"""The frontend, served by the same process as the API when one is present.

The image ships the API alone while the UI is rebuilt, so `locate` finds
nothing there and the root reports it; a checkout still serves the directory
beside it. The index is rewritten on each request to carry the running version
on its asset URLs: without it a browser holds a cached stylesheet across an
upgrade.
"""

import logging
from pathlib import Path
from typing import Final, Self

from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from backend.version import Version

logger = logging.getLogger(__name__)

# A checkout keeps it here; the image ships no frontend, so neither exists there.
REPO_FRONTEND: Final = Path(__file__).resolve().parents[3] / "frontend"
IMAGE_FRONTEND: Final = Path("/app/frontend")

# Versioned URLs, so an upgrade busts the browser cache.
VERSIONED_ASSETS: Final = ("/static/style.css", "/static/app.js")


class Frontend(BaseModel):
    """The frontend directory this process serves, and the page inside it.

    Deploying the API alone is supported, so `locate` answers None rather than
    raising and the root route says so instead of 500ing.
    """

    model_config = ConfigDict(frozen=True)

    directory: Path

    @classmethod
    def locate(cls) -> Self | None:
        """The deployed frontend, checkout before image, or None if absent."""
        for path in (REPO_FRONTEND, IMAGE_FRONTEND):
            if path.exists():
                return cls(directory=path)
        return None

    def index_html(self) -> str | None:
        """The index page with its assets stamped, or None if it is missing."""
        index = self.directory / "index.html"
        if not index.exists():
            return None
        return self.cache_busted(index.read_text())

    @staticmethod
    def cache_busted(html: str) -> str:
        """Stamp the running version onto every versioned asset URL."""
        version = Version.current()
        for asset in VERSIONED_ASSETS:
            html = html.replace(asset, f"{asset}?v={version}")
        return html


def register_static_routes(app: FastAPI) -> None:
    """Mount the frontend, and serve its index at the root.

    The mount is skipped when there is no frontend directory: the API still
    runs, and the root reports it rather than failing.
    """
    frontend = Frontend.locate()

    if frontend is not None:
        app.mount("/static", StaticFiles(directory=frontend.directory), name="static")

    async def _index() -> Response:
        """``GET /`` -- the single page, with cache-busted assets."""
        html = frontend.index_html() if frontend else None
        if html is None:
            return JSONResponse({"message": "MediaSage API is running. Frontend not found."})
        # `no-cache` on the index alone: it is what carries the versioned asset
        # URLs, so a cached copy would keep pointing at the old ones.
        return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

    app.add_api_route("/", _index, methods=["GET"], response_model=None, operation_id="getIndex")
