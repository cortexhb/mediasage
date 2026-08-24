"""``/api/filter/preview`` -- how many tracks one filter selection reaches.

Needs neither Plex nor a model when the library is cached, which is the point
of caching it; a connected server is only the fallback until one exists.
"""

import asyncio

from fastapi import FastAPI, HTTPException

from backend import library
from backend.library import TrackFilter
from backend.models import FilterPreviewRequest, FilterPreviewResponse
from backend.plex import PlexFilter, PlexQueryError, plex_store


async def _preview_filters(
    request: FilterPreviewRequest,
) -> FilterPreviewResponse:
    """``POST /api/filter/preview`` -- how many tracks one selection reaches.

    The cache answers instantly; Plex is the fallback until one exists, and
    only then does this endpoint need a connected server.
    """
    if library.library_sync.has_tracks():
        matching = await asyncio.to_thread(
            library.track_cache.count,
            TrackFilter(
                genres=request.genres or [],
                decades=request.decades or [],
                min_rating=request.min_rating,
                exclude_live=request.exclude_live,
            ),
        )
    else:
        try:
            matching = await asyncio.to_thread(
                plex_store.require().library.count,
                PlexFilter(
                    genres=request.genres or [],
                    decades=request.decades or [],
                    min_rating=request.min_rating,
                    exclude_live=request.exclude_live,
                ),
            )
        except PlexQueryError as err:
            raise HTTPException(status_code=502, detail=str(err)) from err

    return FilterPreviewResponse.of(request, matching)


def register_filter_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/filter/preview",
        _preview_filters,
        methods=["POST"],
        response_model=FilterPreviewResponse,
        operation_id="previewFilters",
    )
