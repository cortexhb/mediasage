"""``/api/generate``, ``/api/playlist``, ``/api/plex`` and ``/api/play-queue``.

Four resources around one playlist: making it, writing it to Plex, reading
what Plex already holds, and playing it. Generation streams because it makes
several LLM calls and the user is watching; everything else is one Plex call.

Modules:
    generate  -- /api/generate -- a playlist, streamed as it is built
    saving    -- /api/playlist -- write a new one, or change an existing one
    server    -- /api/plex -- the playlists and players Plex has now
    queue     -- /api/play-queue -- start tracks on a client
"""

from fastapi import FastAPI

from backend.api.routes.playlists.generate import register_generate_routes
from backend.api.routes.playlists.queue import register_queue_routes
from backend.api.routes.playlists.saving import register_saving_routes
from backend.api.routes.playlists.server import register_server_routes

__all__ = ["register_playlist_routes"]


def register_playlist_routes(app: FastAPI) -> None:
    """Mount all four, in the order the shadowing comments in `saving` assume."""
    register_generate_routes(app)
    register_saving_routes(app)
    register_server_routes(app)
    register_queue_routes(app)
