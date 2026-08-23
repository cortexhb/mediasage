"""``/api/plex`` -- what the Plex server currently has.

Both read straight through to Plex and need a connected server: the playlists
already on it, and the players that could start playing now.
"""

import asyncio
from typing import Annotated

from fastapi import Depends, FastAPI

from backend.plex import PlexClient, PlexClientInfo, PlexPlaylistInfo, plex_store


async def _plex_playlists(
    plex: Annotated[PlexClient, Depends(plex_store.require)],
) -> list[PlexPlaylistInfo]:
    """``GET /api/plex/playlists`` -- audio playlists on the server."""
    return await asyncio.to_thread(plex.playlists.listing)


async def _plex_clients(
    plex: Annotated[PlexClient, Depends(plex_store.require)],
) -> list[PlexClientInfo]:
    """``GET /api/plex/clients`` -- players that could start playing now."""
    return await asyncio.to_thread(plex.playback.clients)


def register_server_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/plex/playlists",
        _plex_playlists,
        methods=["GET"],
        response_model=list[PlexPlaylistInfo],
        operation_id="listPlexPlaylists",
    )
    app.add_api_route(
        "/api/plex/clients",
        _plex_clients,
        methods=["GET"],
        response_model=list[PlexClientInfo],
        operation_id="listPlexClients",
    )
