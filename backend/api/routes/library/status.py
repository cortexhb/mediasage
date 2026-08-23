"""``/api/library/status`` -- what the UI polls while a sync runs.

Answered from SQLite; never touches Plex, so it stays cheap at poll rate.
"""

from typing import Annotated

from fastapi import Depends, FastAPI

from backend import library
from backend.models import LibraryCacheStatusResponse
from backend.plex import plex_store


async def _status(
    plex_connected: Annotated[bool, Depends(plex_store.is_connected)],
) -> LibraryCacheStatusResponse:
    """``GET /api/library/status`` -- what the UI polls while a sync runs."""
    state = library.library_sync.status()
    return LibraryCacheStatusResponse(
        track_count=state.track_count,
        synced_at=state.synced_at,
        is_syncing=state.is_syncing,
        sync_progress=state.sync_progress,
        error=state.error,
        plex_connected=plex_connected,
    )


def register_status_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/library/status",
        _status,
        methods=["GET"],
        response_model=LibraryCacheStatusResponse,
        operation_id="getLibraryStatus",
    )
