"""``/api/playlist`` -- writing a generated playlist back to Plex.

One Plex write each, and both need a connected server.
"""

import asyncio
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from backend.models import SavePlaylistRequest, UpdatePlaylistRequest
from backend.plex import PlaylistResult, PlaylistUpdateResult, PlexClient, plex_store


async def _save_playlist(
    request: SavePlaylistRequest,
    plex: Annotated[PlexClient, Depends(plex_store.require)],
) -> PlaylistResult:
    """``POST /api/playlist`` -- write a new playlist to Plex."""
    return await asyncio.to_thread(
        plex.playlists.create, request.name, request.rating_keys, request.description
    )


async def _update_playlist(
    request: UpdatePlaylistRequest, plex: Annotated[PlexClient, Depends(plex_store.require)]
) -> PlaylistUpdateResult:
    """``POST /api/playlist/update`` -- replace or append to an existing one."""
    result = await asyncio.to_thread(
        plex.playlists.update,
        request.playlist_id,
        request.rating_keys,
        request.mode,
        request.description,
    )
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error or "Playlist update failed")
    return result


def register_saving_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/playlist", _save_playlist, methods=["POST"], response_model=PlaylistResult
    )
    # Before `/api/playlist` would shadow it under a path parameter later.
    app.add_api_route(
        "/api/playlist/update", _update_playlist, methods=["POST"],
        response_model=PlaylistUpdateResult,
    )
