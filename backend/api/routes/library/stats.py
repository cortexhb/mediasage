"""``/api/library/stats`` -- genre and decade counts, cached or live.

The cached form is what the filter chips read and costs no Plex call; the live
form needs a connected server. Mount order between the two is significant.
"""

import asyncio
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from backend import library
from backend.models import LibraryStatsResponse
from backend.plex import PlexClient, PlexQueryError, plex_store


async def _stats(plex: Annotated[PlexClient, Depends(plex_store.require)]) -> LibraryStatsResponse:
    """``GET /api/library/stats`` -- counts read live from Plex."""
    try:
        return await asyncio.to_thread(plex.library.stats)
    except PlexQueryError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err


async def _cached_stats() -> LibraryStatsResponse:
    """``GET /api/library/stats/cached`` -- the filter chips, from SQLite.

    `total_tracks` is left at zero: the chips do not show it, and counting
    would cost a scan the cache exists to avoid.
    """
    stats = await asyncio.to_thread(library.track_cache.genre_decade_stats)
    return LibraryStatsResponse(total_tracks=0, genres=stats.genres, decades=stats.decades)


def register_stats_routes(app: FastAPI) -> None:
    # Before `/api/library/stats` would shadow it, FastAPI matches in mount
    # order and the literal path has to be registered first.
    app.add_api_route(
        "/api/library/stats/cached",
        _cached_stats,
        methods=["GET"],
        response_model=LibraryStatsResponse,
        operation_id="getCachedLibraryStats",
    )
    app.add_api_route(
        "/api/library/stats",
        _stats,
        methods=["GET"],
        response_model=LibraryStatsResponse,
        operation_id="getLibraryStats",
    )
