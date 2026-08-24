"""The single-page app, served by the same process as the API when one is built.

`spa/dist` is a Vite build: an index naming content-hashed files under
`assets/`, plus whatever `spa/public/` contributed at the top level. The image
copies that tree to `/app/frontend`; a checkout serves it where vite wrote it.

Routing is client-side, so a path that matches no file and no API route answers
the index rather than 404ing -- without that, reloading `/settings` is broken.
Deploying the API alone stays supported: `locate` answers None and the root
says so.
"""

import logging
from pathlib import Path
from typing import Final, Self

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

# A checkout has it only after `npm run build`.
REPO_FRONTEND: Final = Path(__file__).resolve().parents[3] / "spa" / "dist"
IMAGE_FRONTEND: Final = Path("/app/frontend")

# Vite content-hashes every name under it, so a hit is never stale.
HASHED: Final = "assets/"
FOREVER: Final = "public, max-age=31536000, immutable"

# A mistyped endpoint must 404, not answer a fetch with HTML.
API_PREFIX: Final = "api/"


class Frontend(BaseModel):
    """The build directory this process serves, and the files inside it."""

    model_config = ConfigDict(frozen=True)

    directory: Path

    @classmethod
    def locate(cls) -> Self | None:
        """The deployed build, checkout before image, or None if absent."""
        for path in (REPO_FRONTEND, IMAGE_FRONTEND):
            if path.exists():
                return cls(directory=path)
        return None

    def index_html(self) -> str | None:
        """The page every client-side route is served as, or None if missing."""
        index = self.directory / "index.html"
        if not index.exists():
            return None
        return index.read_text()

    def file(self, path: str) -> Path | None:
        """The build file a request names, or None when it names none.

        Resolved and contained: a `..` left unresolved would read any file the
        process can.
        """
        root = self.directory.resolve()
        candidate = (root / path).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            return None
        return candidate

    @staticmethod
    def caching(path: str) -> dict[str, str]:
        """How long the browser may hold what `path` named.

        Only the hashed bundles are safe to keep; anything else must revalidate,
        which `FileResponse` arranges with an ETag.
        """
        return {"Cache-Control": FOREVER} if path.startswith(HASHED) else {}


def register_static_routes(app: FastAPI) -> None:
    """Serve the build, and the index for every path the API did not claim.

    Registered last, so the catch-all shadows nothing. Framework-mandated
    shape: FastAPI takes the handler, not an object.
    """
    frontend = Frontend.locate()

    async def _index(path: str = "") -> Response:
        """``GET /{path}`` -- a build file, or the page that routes itself."""
        if path.startswith(API_PREFIX):
            raise HTTPException(status_code=404, detail="Not Found")

        html = frontend.index_html() if frontend else None
        if frontend is None or html is None:
            return JSONResponse({"message": "MediaSage API is running. Frontend not found."})

        file = frontend.file(path)
        if file is not None:
            return FileResponse(file, headers=frontend.caching(path))
        # It names the hashed bundles; a held copy pins the old ones.
        return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

    # Out of the schema: a path that matches everything generates a client
    # function that means nothing.
    app.add_api_route(
        "/{path:path}", _index, methods=["GET"], response_model=None, include_in_schema=False
    )
