"""``/api/recommend/albums/preview`` -- how many albums a round would reach.

Answered from the cache alone: an unsynced library previews as zero albums
rather than as an error, because the number is what the form is asking for.
"""

import asyncio

from fastapi import FastAPI, Query

from backend import library
from backend.library import TrackFilter
from backend.recommender.models import AlbumPreviewResponse


async def _preview(
    genres: str | None = Query(None, description="Comma-separated genre names"),
    decades: str | None = Query(None, description="Comma-separated decade names"),
    max_albums: int = Query(2500, description="Max albums to send to AI"),
) -> AlbumPreviewResponse:
    """``GET /api/recommend/albums/preview`` -- how many albums a round reaches."""
    matching = 0
    if library.library_sync.has_tracks():
        candidates = await asyncio.to_thread(
            library.album_cache.candidates,
            TrackFilter.of_query(genres, decades),
        )
        matching = len(candidates)

    return AlbumPreviewResponse.of(matching, max_albums)


def register_preview_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/recommend/albums/preview",
        _preview,
        methods=["GET"],
        response_model=AlbumPreviewResponse,
        operation_id="previewRecommendAlbums",
    )
