"""Reading the Plex music library: bulk pages for the sync, queries for the UI.

Everything here needs a connected `PlexConnection`; an unconnected one yields
nothing rather than raising, so a disconnected server reads as an empty library
only where the caller has already checked. Entry points: `iter_raw_tracks` and
`album_metadata` for the sync, `filtered`/`count`/`search` for the UI.

Genre and year live on the album in Plex, not on the track, which is why the
sync fetches albums separately instead of reading them per track.
"""

import logging
from collections.abc import Iterator
from typing import Any

from backend.config.store import config_store
from backend.library import AlbumMetadata, LiveVersionRule
from backend.models import LibraryStatsResponse, Track
from backend.plex.connection import PlexConnection, PlexQueryError, with_retries
from backend.plex.filters import PlexFilter

logger = logging.getLogger(__name__)

def configured_page_size() -> int:
    """Rows per Plex request during a bulk fetch, as configured."""
    return config_store.get().plex.page_size


def live_rule() -> LiveVersionRule:
    """The configured live-version test, compiled once per query."""
    return LiveVersionRule.of(config_store.get().library)


def is_live(track: Any, rule: LiveVersionRule) -> bool:
    """Whether a raw Plex track looks like a live recording.

    Reads `parentTitle` rather than calling `track.album()`: the album title is
    already on the listing, and the call would be one HTTP request per track.
    """
    return rule.matches(track.title, getattr(track, "parentTitle", "") or "")


def to_track(plex_track: Any) -> Track:
    """Convert a raw Plex track into the model the API returns."""
    genres = [
        genre.tag if hasattr(genre, "tag") else str(genre)
        for genre in getattr(plex_track, "genres", None) or []
    ]
    year = getattr(plex_track, "parentYear", None) or getattr(plex_track, "year", None)

    return Track(
        rating_key=str(plex_track.ratingKey),
        title=plex_track.title,
        artist=plex_track.grandparentTitle or "Unknown Artist",
        album=plex_track.parentTitle or "Unknown Album",
        duration_ms=plex_track.duration or 0,
        year=year,
        # Art is proxied so the Plex token never reaches the browser.
        art_url=f"/api/art/{plex_track.ratingKey}" if plex_track.ratingKey else None,
        genres=genres,
    )


def total_tracks(connection: PlexConnection) -> int:
    """How many tracks the library holds, or 0 when it cannot be read."""
    if not connection.library:
        return 0
    try:
        return connection.library.totalViewSize(libtype="track")
    except Exception:
        logger.exception("Failed to get library track count")
        return 0


def _pages(connection: PlexConnection, libtype: str, start: int, rows: int) -> Iterator[list[Any]]:
    """Yield one page of `libtype` at a time, retrying each page.

    Raises:
        PlexFetchError: When a page still fails after retries
    """
    offset = start
    while True:
        page = with_retries(
            f"{libtype}s[{offset}:{offset + rows}]",
            lambda o=offset: connection.library.search(
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


def iter_raw_tracks(
    connection: PlexConnection, start: int = 0, page_size: int | None = None
) -> Iterator[list[Any]]:
    """Yield raw track objects a page at a time, starting at an offset.

    Paging is what makes the sync resumable: it checkpoints the offset and
    restarts from `start` rather than refetching the library.

    Args:
        connection: A connected Plex handle; an unconnected one yields nothing
        start: Offset to resume from
        page_size: Rows per request; the configured size by default
    """
    if not connection.library:
        return
    yield from _pages(
        connection, "track", start, configured_page_size() if page_size is None else page_size
    )


def all_raw_tracks(connection: PlexConnection) -> list[Any]:
    """Every raw track object, paged. Empty when the fetch fails."""
    if not connection.library:
        return []
    try:
        return [track for page in iter_raw_tracks(connection) for track in page]
    except Exception:
        logger.exception("Failed to get all tracks")
        return []


def album_metadata(connection: PlexConnection) -> dict[str, AlbumMetadata]:
    """Every album's year and genres, keyed by rating key.

    Raises:
        PlexFetchError: When a page still fails after retries
    """
    if not connection.library:
        return {}

    albums: dict[str, AlbumMetadata] = {}
    for page in _pages(connection, "album", 0, configured_page_size()):
        for album in page:
            albums[str(album.ratingKey)] = AlbumMetadata(year=getattr(album, "year", None))

    _attach_genres(connection, albums)
    return albums


def _attach_genres(connection: PlexConnection, albums: dict[str, AlbumMetadata]) -> None:
    """Fill in each album's genres with one query per genre choice.

    Plex omits Genre tags from section listings, so reading `album.genres`
    costs a request per album -- thousands on a mid-size library. Querying by
    genre instead costs one request per genre, of which there are tens.

    A failure is logged and skipped: a missing genre degrades filtering, it
    does not invalidate the sync.
    """
    try:
        choices = connection.library.listFilterChoices("genre", libtype="album")
    except Exception as error:
        logger.warning("Could not list album genre choices, genres unavailable: %s", error)
        return

    for choice in choices:
        title = getattr(choice, "title", None)
        if not title:
            continue
        try:
            matches = connection.library.search(libtype="album", genre=title)
        except Exception as error:
            logger.warning("Genre query failed for %r: %s", title, error)
            continue
        for album in matches:
            entry = albums.get(str(album.ratingKey))
            if entry is not None:
                entry.genres.append(title)


def stats(connection: PlexConnection) -> LibraryStatsResponse:
    """The genre and decade choices the server offers, with the track total.

    Raises:
        PlexQueryError: When the server cannot be queried. A broken Plex must
            not read as an empty library -- the UI would offer no filters and
            give no reason why.
    """
    if not connection.library:
        raise PlexQueryError("Not connected to a Plex music library")

    try:
        genres = sorted(
            (
                {"name": choice.title, "count": None}
                for choice in connection.library.listFilterChoices("genre", libtype="track")
            ),
            key=lambda genre: genre["name"],
        )
        # The decade filter exists only on albums, never on tracks.
        decades = sorted(
            (
                {"name": _decade_label(choice.title), "count": None}
                for choice in connection.library.listFilterChoices("decade", libtype="album")
            ),
            key=lambda decade: decade["name"],
        )
        return LibraryStatsResponse(
            total_tracks=connection.library.totalViewSize(libtype="track"),
            genres=genres,
            decades=decades,
        )
    except Exception as error:
        raise PlexQueryError(f"Failed to read library stats: {error}") from error


def _decade_label(name: str) -> str:
    """Plex files decades as "1990"; the UI shows "1990s"."""
    return name if not name or name.endswith("s") else f"{name}s"


def filtered(
    connection: PlexConnection, plex_filter: PlexFilter, limit: int = 0
) -> list[Track]:
    """Tracks matching a filter, sampled at random when a limit is set.

    Args:
        connection: Connected Plex handle
        plex_filter: What to ask Plex for, and whether to drop live versions
        limit: Cap on results; 0 returns every match

    Returns:
        Matching tracks, at most `limit` of them

    Raises:
        PlexQueryError: When the query fails
    """
    if not connection.library:
        return []

    kwargs = plex_filter.search_kwargs()
    try:
        if limit > 0:
            # Random sampling keeps a 50k library from being fetched whole.
            found = connection.library.search(
                libtype="track",
                sort="random",
                limit=plex_filter.fetch_count(limit),
                **kwargs,
            )
        else:
            found = connection.library.search(libtype="track", **kwargs)

        if plex_filter.exclude_live:
            rule = live_rule()
            found = [track for track in found if not is_live(track, rule)]

        return [to_track(track) for track in (found[:limit] if limit > 0 else found)]
    except Exception as error:
        logger.exception("Failed to query Plex library with filters: %s", kwargs)
        raise PlexQueryError(f"Failed to query Plex library: {error}") from error


def count(connection: PlexConnection, plex_filter: PlexFilter) -> int:
    """How many tracks match a filter, without building Track models.

    Raises:
        PlexQueryError: When the query fails
    """
    if not connection.library:
        raise PlexQueryError("Not connected to a Plex music library")

    kwargs = plex_filter.search_kwargs()
    try:
        if not kwargs and not plex_filter.exclude_live:
            return connection.library.totalViewSize(libtype="track")

        found = connection.library.search(libtype="track", **kwargs)
        if not plex_filter.exclude_live:
            return len(found)

        rule = live_rule()
        return sum(1 for track in found if not is_live(track, rule))
    except Exception as error:
        logger.exception("Failed to count tracks with filters: %s", kwargs)
        raise PlexQueryError(f"Failed to count tracks: {error}") from error


def random_tracks(connection: PlexConnection, wanted: int, exclude_live: bool = True) -> list[Track]:
    """A random sample of the library, taken server-side.

    Raises:
        PlexQueryError: When the query fails
    """
    return filtered(connection, PlexFilter(exclude_live=exclude_live), limit=wanted)


def search(connection: PlexConnection, query: str, limit: int = 20) -> list[Track]:
    """Tracks whose title or artist matches `query`.

    Titles are searched first; artists fill the remainder, so searching for a
    band returns its tracks even when none of them carry its name.
    """
    if not connection.library:
        return []

    try:
        results = list(connection.library.searchTracks(title=query, limit=limit))
        seen = {track.ratingKey for track in results}

        if len(results) < limit:
            for artist in connection.library.searchArtists(title=query, limit=limit):
                for track in artist.tracks():
                    if track.ratingKey in seen:
                        continue
                    seen.add(track.ratingKey)
                    results.append(track)
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break

        return [to_track(track) for track in results[:limit]]
    except Exception:
        logger.exception("Library search failed for %r", query)
        return []


def track_by_key(connection: PlexConnection, rating_key: str) -> Track | None:
    """One track by rating key, or None when it no longer resolves."""
    if not connection.server:
        return None
    try:
        return to_track(connection.server.fetchItem(int(rating_key)))
    except Exception:
        logger.warning("Could not fetch track %s", rating_key)
        return None


def thumb_path(connection: PlexConnection, rating_key: str) -> str | None:
    """The Plex thumb path for a track, walking track then album then artist.

    Compilations and soundtracks often carry art only on the artist, so
    stopping at the track thumb would leave blank covers.
    """
    if not connection.server:
        return None
    try:
        item = connection.server.fetchItem(int(rating_key))
    except Exception:
        logger.warning("Could not fetch thumb for %s", rating_key)
        return None

    return (
        getattr(item, "thumb", None)
        or getattr(item, "parentThumb", None)
        or getattr(item, "grandparentThumb", None)
    )
