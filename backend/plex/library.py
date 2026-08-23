"""Reading the Plex music library: bulk pages for the sync, queries for the UI.

`PlexLibrary` holds the connection and answers every read; an unconnected one
yields nothing rather than raising, so a disconnected server reads as an empty
library only where the caller has already checked. Entry points:
`PlexLibrary.iter_raw_tracks` and `album_metadata` for the sync,
`filtered`/`count`/`search` for the UI.

Genre and year live on the album in Plex, not on the track, which is why the
sync fetches albums separately instead of reading them per track.
"""

import logging
import threading
import time
from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel, ConfigDict, PrivateAttr

from backend.config.store import config_store
from backend.library import AlbumMetadata, DecadeCount, GenreCount, LiveVersionRule
from backend.models import LibraryStatsResponse, Track
from backend.plex.connection import PlexConnection, PlexQueryError
from backend.plex.filters import PlexFilter

logger = logging.getLogger(__name__)


class PlexLibrary(BaseModel):
    """Every read the application makes against one Plex music library."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    connection: PlexConnection

    # When `stats` last read Plex, and what it got back.
    _stats: tuple[float, LibraryStatsResponse] | None = PrivateAttr(default=None)
    _stats_lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)

    def total_tracks(self) -> int:
        """How many tracks the library holds, or 0 when it cannot be read."""
        if not self.connection.library:
            return 0
        try:
            return self.connection.library.totalViewSize(libtype="track")
        except Exception:
            logger.exception("Failed to get library track count")
            return 0

    def _pages(self, libtype: str, start: int, rows: int) -> Iterator[list[Any]]:
        """Yield one page of `libtype` at a time, retrying each page.

        Raises:
            PlexFetchError: When a page still fails after retries
        """
        offset = start
        while True:
            page = self.connection.with_retries(
                f"{libtype}s[{offset}:{offset + rows}]",
                lambda o=offset: self.connection.library.search(
                    libtype=libtype,
                    container_start=o,
                    container_size=rows,
                    maxresults=rows,
                ),
            )
            if not page:
                return
            yield page
            if len(page) < rows:
                return
            offset += rows

    def iter_raw_tracks(self, start: int = 0) -> Iterator[list[Any]]:
        """Yield raw track objects a page at a time, starting at an offset.

        Paging is what makes the sync resumable: it checkpoints the offset and
        restarts from `start` rather than refetching the library.

        Args:
            start: Offset to resume from
        """
        if not self.connection.library:
            return
        yield from self._pages("track", start, config_store.get().plex.page_size)

    def all_raw_tracks(self) -> list[Any]:
        """Every raw track object, paged. Empty when the fetch fails."""
        if not self.connection.library:
            return []
        try:
            return [track for page in self.iter_raw_tracks() for track in page]
        except Exception:
            logger.exception("Failed to get all tracks")
            return []

    def album_metadata(self) -> dict[str, AlbumMetadata]:
        """Every album's year and genres, keyed by rating key.

        Raises:
            PlexFetchError: When a page still fails after retries
        """
        if not self.connection.library:
            return {}

        albums: dict[str, AlbumMetadata] = {}
        for page in self._pages("album", 0, config_store.get().plex.page_size):
            for album in page:
                albums[str(album.ratingKey)] = AlbumMetadata(year=getattr(album, "year", None))

        self._attach_genres(albums)
        return albums

    def _attach_genres(self, albums: dict[str, AlbumMetadata]) -> None:
        """Fill in each album's genres with one query per genre choice.

        Plex omits Genre tags from section listings, so reading `album.genres`
        costs a request per album -- thousands on a mid-size library. Querying by
        genre instead costs one request per genre, of which there are tens.

        A failure is logged and skipped: a missing genre degrades filtering, it
        does not invalidate the sync.
        """
        try:
            choices = self.connection.library.listFilterChoices("genre", libtype="album")
        except Exception as error:
            logger.warning("Could not list album genre choices, genres unavailable: %s", error)
            return

        for choice in choices:
            title = getattr(choice, "title", None)
            if not title:
                continue
            try:
                matches = self.connection.library.search(libtype="album", genre=title)
            except Exception as error:
                logger.warning("Genre query failed for %r: %s", title, error)
                continue
            for album in matches:
                entry = albums.get(str(album.ratingKey))
                if entry is not None:
                    entry.genres.append(title)

    def stats(self) -> LibraryStatsResponse:
        """The genre and decade choices the server offers, with the track total.

        Held for `library.stats_cache_seconds` between reads. Plex aggregates
        genre tags across every track to answer this, measured at 8.75s over an
        80k library, and the answer only moves when the library does.

        Raises:
            PlexQueryError: When the server cannot be queried. A broken Plex must
                not read as an empty library -- the UI would offer no filters and
                give no reason why.
        """
        if not self.connection.library:
            raise PlexQueryError("Not connected to a Plex music library")

        held = config_store.get().library.stats_cache_seconds
        with self._stats_lock:
            cached = self._stats
            if cached is not None and time.monotonic() - cached[0] < held:
                return cached[1]

        fresh = self._read_stats()
        with self._stats_lock:
            self._stats = (time.monotonic(), fresh)
        return fresh

    def _read_stats(self) -> LibraryStatsResponse:
        """The three Plex reads behind `stats`, with nothing held."""
        try:
            genres = sorted(
                (
                    GenreCount(name=choice.title)
                    for choice in self.connection.library.listFilterChoices(
                        "genre", libtype="track"
                    )
                ),
                key=lambda genre: genre.name,
            )
            # The decade filter exists only on albums, never on tracks.
            decades = sorted(
                (
                    DecadeCount.of_plex(choice.title)
                    for choice in self.connection.library.listFilterChoices(
                        "decade", libtype="album"
                    )
                ),
                key=lambda decade: decade.name,
            )
            return LibraryStatsResponse(
                total_tracks=self.connection.library.totalViewSize(libtype="track"),
                genres=genres,
                decades=decades,
            )
        except Exception as error:
            raise PlexQueryError(f"Failed to read library stats: {error}") from error

    def filtered(self, plex_filter: PlexFilter, limit: int = 0) -> list[Track]:
        """Tracks matching a filter, sampled at random when a limit is set.

        Args:
            plex_filter: What to ask Plex for, and whether to drop live versions
            limit: Cap on results; 0 returns every match

        Returns:
            Matching tracks, at most `limit` of them

        Raises:
            PlexQueryError: When the query fails
        """
        if not self.connection.library:
            return []

        kwargs = plex_filter.search_kwargs()
        try:
            if limit > 0:
                # Random sampling keeps a 50k library from being fetched whole.
                found = self.connection.library.search(
                    libtype="track",
                    sort="random",
                    limit=plex_filter.fetch_count(limit),
                    **kwargs,
                )
            else:
                found = self.connection.library.search(libtype="track", **kwargs)

            if plex_filter.exclude_live:
                rule = LiveVersionRule.of(config_store.get().library)
                found = [track for track in found if not rule.matches_plex(track)]

            return [Track.of_plex(track) for track in (found[:limit] if limit > 0 else found)]
        except Exception as error:
            logger.exception("Failed to query Plex library with filters: %s", kwargs)
            raise PlexQueryError(f"Failed to query Plex library: {error}") from error

    def count(self, plex_filter: PlexFilter) -> int:
        """How many tracks match a filter, without building Track models.

        Raises:
            PlexQueryError: When the query fails
        """
        if not self.connection.library:
            raise PlexQueryError("Not connected to a Plex music library")

        kwargs = plex_filter.search_kwargs()
        try:
            if not kwargs and not plex_filter.exclude_live:
                return self.connection.library.totalViewSize(libtype="track")

            found = self.connection.library.search(libtype="track", **kwargs)
            if not plex_filter.exclude_live:
                return len(found)

            rule = LiveVersionRule.of(config_store.get().library)
            return sum(1 for track in found if not rule.matches_plex(track))
        except Exception as error:
            logger.exception("Failed to count tracks with filters: %s", kwargs)
            raise PlexQueryError(f"Failed to count tracks: {error}") from error

    def random_tracks(self, wanted: int, exclude_live: bool = True) -> list[Track]:
        """A random sample of the library, taken server-side.

        Raises:
            PlexQueryError: When the query fails
        """
        return self.filtered(PlexFilter(exclude_live=exclude_live), limit=wanted)

    def search(self, query: str, limit: int = 20) -> list[Track]:
        """Tracks whose title or artist matches `query`.

        Titles are searched first; artists fill the remainder, so searching for a
        band returns its tracks even when none of them carry its name.
        """
        if not self.connection.library:
            return []

        try:
            results = list(self.connection.library.searchTracks(title=query, limit=limit))
            seen = {track.ratingKey for track in results}

            if len(results) < limit:
                for artist in self.connection.library.searchArtists(title=query, limit=limit):
                    for track in artist.tracks():
                        if track.ratingKey in seen:
                            continue
                        seen.add(track.ratingKey)
                        results.append(track)
                        if len(results) >= limit:
                            break
                    if len(results) >= limit:
                        break

            return [Track.of_plex(track) for track in results[:limit]]
        except Exception:
            logger.exception("Library search failed for %r", query)
            return []

    def track_by_key(self, rating_key: str) -> Track | None:
        """One track by rating key, or None when it no longer resolves."""
        if not self.connection.server:
            return None
        try:
            return Track.of_plex(self.connection.server.fetchItem(int(rating_key)))
        except Exception:
            logger.warning("Could not fetch track %s", rating_key)
            return None

    def thumb_path(self, rating_key: str) -> str | None:
        """The Plex thumb path for a track, walking track then album then artist.

        Compilations and soundtracks often carry art only on the artist, so
        stopping at the track thumb would leave blank covers.
        """
        if not self.connection.server:
            return None
        try:
            item = self.connection.server.fetchItem(int(rating_key))
        except Exception:
            logger.warning("Could not fetch thumb for %s", rating_key)
            return None

        return (
            getattr(item, "thumb", None)
            or getattr(item, "parentThumb", None)
            or getattr(item, "grandparentThumb", None)
        )
