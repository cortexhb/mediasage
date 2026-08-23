"""``/api/recommend/albums/preview`` -- what a round would cost.

Answered from the cache alone: an unsynced library previews as zero albums
rather than as an error, because the number is what the form is asking for.
"""

import asyncio
from typing import Annotated

from fastapi import Depends, FastAPI, Query

from backend import library
from backend.api.estimates import AlbumPreviewResponse
from backend.config import MediasageConfig, config_store
from backend.library import TrackFilter


async def _preview(
    config: Annotated[MediasageConfig, Depends(config_store.get)],
    genres: str | None = Query(None, description="Comma-separated genre names"),
    decades: str | None = Query(None, description="Comma-separated decade names"),
    max_albums: int = Query(2500, description="Max albums to send to AI"),
) -> AlbumPreviewResponse:
    """``GET /api/recommend/albums/preview`` -- what a round would cost."""
    matching = 0
    if library.library_sync.has_tracks():
        candidates = await asyncio.to_thread(
            library.album_cache.candidates,
            TrackFilter.of_query(genres, decades),
        )
        matching = len(candidates)

    return AlbumPreviewResponse.of(matching, max_albums, config)


def register_preview_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/recommend/albums/preview", _preview, methods=["GET"],
        response_model=AlbumPreviewResponse,
    )
