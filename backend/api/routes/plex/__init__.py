"""``/api/plex`` -- the browser sign-in that replaces typing a URL and token.

    link.py  -- /api/plex/link and /api/plex/server -- the pin exchange,
                the server picker, and signing out

Nothing else writes the Plex identity. `POST /api/config` carries only
`music_library`; see `docs/plex_login.md`.
"""

from fastapi import FastAPI

from backend.api.routes.plex.link import register_plex_link_routes

__all__ = ["register_plex_routes"]


def register_plex_routes(app: FastAPI) -> None:
    """Mount the sign-in, keeping one entry point for `app.py`."""
    register_plex_link_routes(app)
