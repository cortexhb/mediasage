"""``/api/library`` -- the local mirror of the Plex library.

Status and cached stats are answered from SQLite and never touch Plex. Sync and
search do, so both require a connected server.
"""

import asyncio
from typing import Final

from fastapi import FastAPI, HTTPException, Query

from backend import library
from backend.api import background, guards
from backend.models import (
    LibraryCacheStatusResponse,
    LibraryStatsResponse,
    SyncTriggerResponse,
    Track,
)
from backend.plex import PlexQueryError

# iOS auto-correction turns a typed quote into a curly one, which matches
# nothing in the library.
SMART_QUOTES: Final = str.maketrans(
    {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'}
)


async def _status() -> LibraryCacheStatusResponse:
    """``GET /api/library/status`` -- what the UI polls while a sync runs."""
    state = library.sync_status()
    return LibraryCacheStatusResponse(
        track_count=state.track_count,
        synced_at=state.synced_at,
        is_syncing=state.is_syncing,
        sync_progress=state.sync_progress,
        error=state.error,
        plex_connected=guards.plex_client() is not None,
    )


async def _sync(plex: guards.Plex) -> SyncTriggerResponse:
    """``POST /api/library/sync`` -- start a sync in the background.

    Always backgrounded, so the caller can poll progress rather than holding a
    request open for the length of a full library read.
    """
    if library.library_sync.snapshot().is_syncing:
        raise HTTPException(status_code=409, detail="Sync already in progress")

    background.spawn(asyncio.to_thread(library.library_sync.run, plex))
    return SyncTriggerResponse(started=True, blocking=False)


async def _stats(plex: guards.Plex) -> LibraryStatsResponse:
    """``GET /api/library/stats`` -- counts read live from Plex."""
    try:
        return await asyncio.to_thread(plex.stats)
    except PlexQueryError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err


async def _cached_stats() -> LibraryStatsResponse:
    """``GET /api/library/stats/cached`` -- the filter chips, from SQLite.

    `total_tracks` is left at zero: the chips do not show it, and counting
    would cost a scan the cache exists to avoid.
    """
    stats = await asyncio.to_thread(library.tracks.genre_decade_stats)
    return LibraryStatsResponse(total_tracks=0, genres=stats.genres, decades=stats.decades)


async def _search(
    plex: guards.Plex, q: str = Query(..., description="Search query")
) -> list[Track]:
    """``GET /api/library/search`` -- tracks matching a query, from Plex."""
    return await asyncio.to_thread(plex.search, q.translate(SMART_QUOTES))


def register_library_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/library/status", _status, methods=["GET"],
        response_model=LibraryCacheStatusResponse,
    )
    app.add_api_route(
        "/api/library/sync", _sync, methods=["POST"], response_model=SyncTriggerResponse
    )
    # Before `/api/library/stats` would shadow it, FastAPI matches in mount
    # order and the literal path has to be registered first.
    app.add_api_route(
        "/api/library/stats/cached", _cached_stats, methods=["GET"],
        response_model=LibraryStatsResponse,
    )
    app.add_api_route(
        "/api/library/stats", _stats, methods=["GET"], response_model=LibraryStatsResponse
    )
    app.add_api_route(
        "/api/library/search", _search, methods=["GET"], response_model=list[Track]
    )
