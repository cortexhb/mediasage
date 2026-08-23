"""``/api/results`` -- the saved history of playlists and recommendations.

Modules:
    listing  -- GET /api/results -- one page, filtered by type
    detail   -- /api/results/{result_id} -- read one, or forget it
"""

from fastapi import FastAPI

from backend.api.routes.results.detail import register_detail_routes
from backend.api.routes.results.listing import register_listing_routes

__all__ = ["register_results_routes"]


def register_results_routes(app: FastAPI) -> None:
    """Mount both, the collection before the path parameter that follows it."""
    register_listing_routes(app)
    register_detail_routes(app)
