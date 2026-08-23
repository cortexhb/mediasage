"""``/api/library`` -- the local mirror of the Plex library.

Status and cached stats are answered from SQLite and never touch Plex. Sync,
live stats and search do, so those require a connected server.

Modules:
    status  -- /api/library/status -- what the UI polls while a sync runs
    sync    -- /api/library/sync -- start one in the background
    stats   -- /api/library/stats -- genre and decade counts, cached or live
    search  -- /api/library/search -- tracks matching a query, from Plex
"""

from fastapi import FastAPI

from backend.api.routes.library.search import register_search_routes
from backend.api.routes.library.stats import register_stats_routes
from backend.api.routes.library.status import register_status_routes
from backend.api.routes.library.sync import register_sync_routes

__all__ = ["register_library_routes"]


def register_library_routes(app: FastAPI) -> None:
    """Mount all four, in the order the shadowing comment in `stats` assumes."""
    register_status_routes(app)
    register_sync_routes(app)
    register_stats_routes(app)
    register_search_routes(app)
