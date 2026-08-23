"""Matching an album a model named back to one we actually have.

A model rarely returns a title byte-for-byte: it drops "(Reissue)", writes
"and" for "&", or loses an accent. Three passes, cheapest first -- exact key,
then substring, then fuzzy -- so an exact answer costs a dict lookup.

Entry points: `AlbumMatcher.for_selection` and `AlbumMatcher.for_pitches`.
"""

import logging
from typing import Any, Self

from backend.config.store import config_store
from backend.recommender.models import AlbumRef
from backend.utils import FuzzyMatcher

logger = logging.getLogger(__name__)


class AlbumMatcher(FuzzyMatcher):
    """How close a name has to be before it counts as the same album.

    Scores are rapidfuzz ratios over simplified text, 0-100. A candidate must
    clear every configured floor; among those that do, the highest combined
    score wins.
    """

    artist_min: int
    combined_min: int = 0
    album_min: int = 0

    @classmethod
    def for_selection(cls) -> Self:
        """Picking a library album from what the model chose.

        A wrong match here plays the wrong record, so both halves of the name
        have to hold up.
        """
        matching = config_store.get().matching
        return cls(artist_min=matching.album_artist_min, combined_min=matching.album_combined_min)

    @classmethod
    def for_pitches(cls) -> Self:
        """Attaching a written pitch to the album it was written for.

        The album list was in the prompt, so the artist is near-certain and
        only the title is at risk of having been truncated.
        """
        matching = config_store.get().matching
        return cls(artist_min=matching.pitch_artist_min, album_min=matching.pitch_album_min)

    def find(self, wanted: AlbumRef, entries: dict[str, Any]) -> Any | None:
        """The entry `wanted` names, or None when nothing is close enough.

        Args:
            wanted: The album as the model named it
            entries: Candidates keyed by `AlbumRef.key`

        Returns:
            The matching value from `entries`, or None
        """
        exact = entries.get(wanted.key)
        if exact is not None:
            return exact

        return self._by_substring(wanted, entries) or self._by_score(wanted, entries)

    def _by_substring(self, wanted: AlbumRef, entries: dict[str, Any]) -> Any | None:
        """Same artist, and one album title contained in the other.

        Catches the common case of a dropped suffix -- "Ágætis byrjun" against
        "Ágætis byrjun (Reissue)" -- without paying for a fuzzy sweep.
        """
        artist = wanted.artist.lower()
        album = wanted.album.lower()
        for key in entries:
            candidate = AlbumRef.parse(key)
            if candidate is None or candidate.artist != artist:
                continue
            if album in candidate.album or candidate.album in album:
                return entries[key]
        return None

    def _by_score(self, wanted: AlbumRef, entries: dict[str, Any]) -> Any | None:
        """The closest candidate clearing every floor."""
        best: Any | None = None
        best_score = 0.0
        for key, value in entries.items():
            candidate = AlbumRef.parse(key)
            if candidate is None:
                continue

            artist_score = self.ratio(wanted.artist, candidate.artist)
            if artist_score < self.artist_min:
                continue
            album_score = self.ratio(wanted.album, candidate.album)
            if album_score < self.album_min:
                continue
            combined = (artist_score + album_score) / 2
            if combined < self.combined_min or combined <= best_score:
                continue

            best, best_score = value, combined

        if best is not None:
            logger.info("Fuzzy matched %s (score: %.0f)", wanted, best_score)
        return best
