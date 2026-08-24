"""The shapes one generation passes between its steps.

`TrackPool` is the filter-first principle as one object: the same few values
become a `TrackFilter` against the local cache or a `PlexFilter` against the
server, whichever can answer, so a 50k library is narrowed before it reaches a
prompt rather than after. `TrackMatcher` then takes what the model named back
to a library track, and `Narrative` titles the result.
"""

import logging
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict

from backend import library
from backend.cancellation import Abandoned
from backend.config import config_store
from backend.generator import prompts
from backend.library import TrackFilter
from backend.llm import LLMClient
from backend.models import Track
from backend.plex import PlexClient, PlexFilter
from backend.utils import FuzzyMatcher

logger = logging.getLogger(__name__)

# Fetched when no ceiling set; a whole library never fits a prompt.
DEFAULT_POOL_LIMIT = 2000


class TrackPool(BaseModel):
    """The tracks a generation may choose between, and how they are found."""

    model_config = ConfigDict(frozen=True)

    genres: list[str] = []
    decades: list[str] = []
    min_rating: int = 0
    exclude_live: bool = True
    # 0 means the caller set no ceiling; `DEFAULT_POOL_LIMIT` applies instead.
    limit: int = 0

    @property
    def is_filtered(self) -> bool:
        """Whether anything narrows the library.

        An unfiltered pool is sampled at random rather than queried, which is
        what keeps a prompt-less generation off a full library scan.
        """
        return bool(self.genres or self.decades or self.min_rating > 0)

    @property
    def size(self) -> int:
        """How many tracks to fetch, with the ceiling applied."""
        return self.limit if self.limit > 0 else DEFAULT_POOL_LIMIT

    def tracks(self, plex: PlexClient) -> list[Track]:
        """The pool itself, from the cache when there is one and Plex otherwise.

        Raises:
            PlexQueryError: When the cache cannot answer and Plex will not
        """
        if library.library_sync.has_tracks():
            cached = library.track_cache.filtered(
                TrackFilter(
                    genres=self.genres,
                    decades=self.decades,
                    min_rating=self.min_rating,
                    exclude_live=self.exclude_live,
                ),
                limit=self.size,
            )
            return [Track.of_cached(row) for row in cached]

        if not self.is_filtered:
            return plex.library.random_tracks(self.size, exclude_live=self.exclude_live)

        return plex.library.filtered(
            PlexFilter(
                genres=self.genres,
                decades=self.decades,
                min_rating=self.min_rating,
                exclude_live=self.exclude_live,
            ),
            limit=self.size,
        )


class TrackMatcher(FuzzyMatcher):
    """How close a named track has to be before it is one the library holds."""

    floor: int

    @classmethod
    def configured(cls) -> Self:
        """A matcher at the configured floor.

        Read once per generation rather than per track: it cannot change
        mid-run, and a generation matches thousands of pairs.
        """
        return cls(floor=config_store.get().matching.track_threshold)

    @staticmethod
    def variants(name: str) -> list[str]:
        """Spellings of one artist name that libraries use interchangeably.

        Only the ampersand split matters in practice: "Hall and Oates" and
        "Hall & Oates" are the same act filed two ways.
        """
        variants = [name]
        if " and " in name.lower():
            variants.append(name.replace(" and ", " & ").replace(" And ", " & "))
        elif " & " in name:
            variants.append(name.replace(" & ", " and "))
        return variants

    def matches(self, artist: str, title: str, track: Track) -> bool:
        """Whether `track` is the one a model named `artist` and `title`.

        Args:
            artist: The artist as the model wrote it
            title: The title as the model wrote it
            track: A candidate from the pool

        Returns:
            True when both halves clear the floor
        """
        if self.ratio(title, track.title) < self.floor:
            return False

        return any(
            self.ratio(variant, track.artist) >= self.floor for variant in self.variants(artist)
        )


class Narrative(BaseModel):
    """The title and the few sentences a finished playlist is presented with."""

    model_config = ConfigDict(frozen=True)

    title: str
    text: str = ""

    @classmethod
    def of(
        cls,
        track_selections: list[dict],
        llm_client: LLMClient,
        user_request: str = "",
        session: str = "",
    ) -> Self:
        """Write one, falling back to a dated title when the model will not.

        The analysis model is used rather than the generation one: this is the
        only creative writing in a run, and it is three sentences.

        Args:
            track_selections: What the model picked, as it returned them
            llm_client: The client to ask
            user_request: The original prompt, for context

        Returns:
            A narrative; on any failure, "{Mon YYYY} Playlist" and no text
        """
        date_suffix = datetime.now().strftime("%b %Y")
        fallback = cls(title=f"{date_suffix} Playlist")

        try:
            response = llm_client.analyze(
                prompts.narrative(track_selections, user_request),
                prompts.NARRATIVE_SYSTEM,
                session,
            )
            result = response.parsed()
        except Abandoned:
            # A dated title is not a better answer than stopping here.
            raise
        except Exception as e:
            logger.warning("Narrative generation failed: %s", e)
            return fallback

        # Some models wrap the object in a single-element array.
        if isinstance(result, list) and result:
            result = result[0]

        if not isinstance(result, dict):
            logger.warning("Narrative response not a dict: %s", type(result).__name__)
            return fallback

        # Models pick a different key for each half about half the time.
        title = cls._first(result, "title", "playlist_title", "name")
        text = cls._first(result, "narrative", "description", "text", "content")

        if not title:
            logger.warning("Narrative title missing. Keys: %s", list(result.keys()))
            # The prose is kept: a dated title is better than losing both.
            return cls(title=fallback.title, text=text)
        if not text:
            logger.warning("Narrative missing from response. Keys: %s", list(result.keys()))

        return cls(title=f"{title} - {date_suffix}", text=text)

    @staticmethod
    def _first(result: dict, *keys: str) -> str:
        """The first of `keys` the model actually filled in, stripped."""
        for key in keys:
            value = str(result.get(key) or "").strip()
            if value:
                return value
        return ""
