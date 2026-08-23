"""``/api/art`` and ``/api/external-art`` -- album art, proxied.

Two sources, proxied for different reasons: Plex art so the token never
reaches the browser, external art so the page does not hotlink a CDN and
because the browser cannot follow the archive's redirect chain for us.

Modules:
    caching   -- how long a browser may keep one image; shared by both
    plex      -- /api/art -- one track's cover, from Plex
    external  -- /api/external-art -- one cover from the Cover Art Archive
"""

from fastapi import FastAPI

from backend.api.routes.art.caching import CachePolicy
from backend.api.routes.art.external import ExternalArt, register_external_art_routes
from backend.api.routes.art.plex import register_plex_art_routes

__all__ = ["CachePolicy", "ExternalArt", "register_art_routes"]


def register_art_routes(app: FastAPI) -> None:
    """Mount both proxies, keeping one entry point for `app.py`."""
    register_plex_art_routes(app)
    register_external_art_routes(app)
