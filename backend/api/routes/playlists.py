"""``/api/generate``, ``/api/playlist`` and ``/api/play-queue`` -- playlists.

Generation streams because it makes several LLM calls and the user is watching.
Everything else here is one Plex write, and every one of them needs a connected
server.
"""

import asyncio

from fastapi import FastAPI, HTTPException
from starlette.responses import StreamingResponse

from backend.api import guards, sse
from backend.generator import generate_playlist_stream
from backend.models import (
    GenerateRequest,
    PlayQueueRequest,
    SavePlaylistRequest,
    UpdatePlaylistRequest,
)
from backend.plex import (
    PlaylistResult,
    PlaylistUpdateResult,
    PlayQueueResult,
    PlexClientInfo,
    PlexPlaylistInfo,
)


async def _generate(
    request: GenerateRequest, plex: guards.Plex, llm: guards.LLM
) -> StreamingResponse:
    """``POST /api/generate/stream`` -- a playlist, with progress.

    The seed track is resolved before the stream opens, so a bad rating key is
    a 404 rather than an error frame the user has to read.
    """
    seed_track = None
    selected_dimensions = None
    if request.seed_track:
        seed_track = await asyncio.to_thread(plex.track_by_key, request.seed_track.rating_key)
        if not seed_track:
            raise HTTPException(status_code=404, detail="Seed track not found")
        selected_dimensions = request.seed_track.selected_dimensions

    def events():
        yield from generate_playlist_stream(
            prompt=request.prompt,
            seed_track=seed_track,
            selected_dimensions=selected_dimensions,
            additional_notes=request.additional_notes,
            refinement_answers=request.refinement_answers,
            genres=request.genres,
            decades=request.decades,
            track_count=request.track_count,
            exclude_live=request.exclude_live,
            min_rating=request.min_rating,
            max_tracks_to_ai=request.max_tracks_to_ai,
        )

    return sse.stream(events())


async def _save_playlist(request: SavePlaylistRequest, plex: guards.Plex) -> PlaylistResult:
    """``POST /api/playlist`` -- write a new playlist to Plex."""
    return await asyncio.to_thread(
        plex.create_playlist, request.name, request.rating_keys, request.description
    )


async def _update_playlist(
    request: UpdatePlaylistRequest, plex: guards.Plex
) -> PlaylistUpdateResult:
    """``POST /api/playlist/update`` -- replace or append to an existing one."""
    result = await asyncio.to_thread(
        plex.update_playlist,
        request.playlist_id,
        request.rating_keys,
        request.mode,
        request.description,
    )
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error or "Playlist update failed")
    return result


async def _plex_playlists(plex: guards.Plex) -> list[PlexPlaylistInfo]:
    """``GET /api/plex/playlists`` -- audio playlists on the server."""
    return await asyncio.to_thread(plex.playlists)


async def _plex_clients(plex: guards.Plex) -> list[PlexClientInfo]:
    """``GET /api/plex/clients`` -- players that could start playing now."""
    return await asyncio.to_thread(plex.clients)


async def _play_queue(request: PlayQueueRequest, plex: guards.Plex) -> PlayQueueResult:
    """``POST /api/play-queue`` -- queue tracks and start them on a client.

    A client that has gone offline between listing and playing is a 404, not a
    server error: the user can pick another one.
    """
    result = await asyncio.to_thread(
        plex.play_queue, request.rating_keys, request.client_id, request.mode
    )
    if not result.success:
        error = result.error or "Play queue creation failed"
        status = 404 if result.error_code == "not_found" else 500
        raise HTTPException(status_code=status, detail=error)
    return result


def register_playlist_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/generate/stream", _generate, methods=["POST"], response_model=None
    )
    app.add_api_route(
        "/api/playlist", _save_playlist, methods=["POST"], response_model=PlaylistResult
    )
    # Before `/api/playlist` would shadow it under a path parameter later.
    app.add_api_route(
        "/api/playlist/update", _update_playlist, methods=["POST"],
        response_model=PlaylistUpdateResult,
    )
    app.add_api_route(
        "/api/plex/playlists", _plex_playlists, methods=["GET"],
        response_model=list[PlexPlaylistInfo],
    )
    app.add_api_route(
        "/api/plex/clients", _plex_clients, methods=["GET"], response_model=list[PlexClientInfo]
    )
    app.add_api_route(
        "/api/play-queue", _play_queue, methods=["POST"], response_model=PlayQueueResult
    )
