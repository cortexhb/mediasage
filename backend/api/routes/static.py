"""The frontend, served by the same process as the API.

One container serves both, so there is no separate web server and no CORS.
The index is rewritten on each request to carry the running version on its
asset URLs: without it a browser holds a cached stylesheet across an upgrade.
"""

import logging
from pathlib import Path
from typing import Final

from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.version import get_version

logger = logging.getLogger(__name__)

# Where the frontend lives in a checkout, and where the image puts it.
REPO_FRONTEND: Final = Path(__file__).resolve().parents[3] / "frontend"
IMAGE_FRONTEND: Final = Path("/app/frontend")

# Assets whose URL carries the version, so an upgrade busts the browser cache.
VERSIONED_ASSETS: Final = ("/static/style.css", "/static/app.js")


def frontend_dir() -> Path | None:
    """Where the frontend is, or None when only the API was deployed."""
    for path in (REPO_FRONTEND, IMAGE_FRONTEND):
        if path.exists():
            return path
    return None


def _cache_busted(html: str) -> str:
    """Stamp the running version onto every asset URL."""
    version = get_version()
    for asset in VERSIONED_ASSETS:
        html = html.replace(asset, f"{asset}?v={version}")
    return html


def register_static_routes(app: FastAPI) -> None:
    """Mount the frontend, and serve its index at the root.

    Both are skipped when there is no frontend directory: the API still runs,
    and the root says so rather than 500ing.
    """
    directory = frontend_dir()

    if directory is not None:
        app.mount("/static", StaticFiles(directory=directory), name="static")

    async def _index() -> Response:
        """``GET /`` -- the single page, with cache-busted assets."""
        index = directory / "index.html" if directory else None
        if index is None or not index.exists():
            return JSONResponse(
                {"message": "MediaSage API is running. Frontend not found."}
            )
        # `no-cache` on the index alone: it is what carries the versioned asset
        # URLs, so a cached copy would keep pointing at the old ones.
        return HTMLResponse(
            _cache_busted(index.read_text()), headers={"Cache-Control": "no-cache"}
        )

    app.add_api_route("/", _index, methods=["GET"], response_model=None)
