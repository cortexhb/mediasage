"""``/api/library/sync`` -- start a sync in the background.

Always backgrounded, so the caller polls `/api/library/status` rather than
holding a request open for the length of a full library read.
"""

import asyncio
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from backend import library
from backend.api.background import background
from backend.models import SyncTriggerResponse
from backend.plex import PlexClient, plex_store


async def _sync(plex: Annotated[PlexClient, Depends(plex_store.require)]) -> SyncTriggerResponse:
    """``POST /api/library/sync`` -- start a sync in the background.

    Always backgrounded, so the caller can poll progress rather than holding a
    request open for the length of a full library read.
    """
    if library.library_sync.snapshot().is_syncing:
        raise HTTPException(status_code=409, detail="Sync already in progress")

    background.spawn(asyncio.to_thread(library.library_sync.run, plex))
    return SyncTriggerResponse(started=True, blocking=False)


def register_sync_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/library/sync",
        _sync,
        methods=["POST"],
        response_model=SyncTriggerResponse,
        operation_id="syncLibrary",
    )
