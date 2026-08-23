"""``/api/play-queue`` -- queue tracks and start them on a client."""

import asyncio
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from backend.models import PlayQueueRequest
from backend.plex import PlayQueueResult, PlexClient, plex_store


async def _play_queue(
    request: PlayQueueRequest, plex: Annotated[PlexClient, Depends(plex_store.require)]
) -> PlayQueueResult:
    """``POST /api/play-queue`` -- queue tracks and start them on a client.

    A client that has gone offline between listing and playing is a 404, not a
    server error: the user can pick another one.
    """
    result = await asyncio.to_thread(
        plex.playback.play_queue, request.rating_keys, request.client_id, request.mode
    )
    if not result.success:
        error = result.error or "Play queue creation failed"
        status = 404 if result.error_code == "not_found" else 500
        raise HTTPException(status_code=status, detail=error)
    return result


def register_queue_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/play-queue",
        _play_queue,
        methods=["POST"],
        response_model=PlayQueueResult,
        operation_id="createPlayQueue",
    )
