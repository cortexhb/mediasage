"""Assemble the MediaSage FastAPI application.

`create_app()` is the whole entry point: it builds the app and mounts each
route module in turn. A factory rather than a module-scope `app` so nothing is
read from the config singleton at import time, and so a test can build a fresh
application without the one the process already holds.

Startup and shutdown live in `lifespan`: both clients are built from whatever
is configured, and the schema is brought to head before anything reads it.

A route that needs a dependency depends on it and does not check for it: the
handler registered here turns "there is no Plex" and "there is no provider"
into a 503, wherever they are raised.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.api.clients import shared
from backend.api.routes.analyze import register_analyze_routes
from backend.api.routes.art import register_art_routes
from backend.api.routes.config import register_config_routes
from backend.api.routes.health import register_health_routes
from backend.api.routes.library import register_library_routes
from backend.api.routes.playlists import register_playlist_routes
from backend.api.routes.recommend import register_recommend_routes
from backend.api.routes.results import register_results_routes
from backend.api.routes.setup import register_setup_routes
from backend.api.routes.static import register_static_routes
from backend.config import config_store
from backend.db import migrations
from backend.llm import LLMClient, LLMNotConfigured, client_store
from backend.plex import PlexClient, PlexNotConnected, plex_store
from backend.version import Version

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Build what is configured, then release it on the way out."""
    config = config_store.get()

    if config.plex.url and config.plex.token:
        plex_store.client = PlexClient.of(config.plex)

    if config.llm.is_configured:
        client_store.client = LLMClient.of(config.llm)

    # Before anything reads or writes a row.
    migrations.upgrade_to_head()

    yield

    await shared.close()


async def _unavailable(request: Request, exc: Exception) -> JSONResponse:
    """A dependency that was never configured, as a status code.

    503 rather than 500: nothing is broken, something has not been set up, and
    the UI sends the user to Settings on this.
    """
    return JSONResponse(status_code=503, content={"detail": str(exc)})


def create_app() -> FastAPI:
    """Build the application and mount every route on it."""
    app = FastAPI(
        title="MediaSage",
        description="Plex playlist generator powered by LLMs",
        version=Version.current(),
        lifespan=lifespan,
    )

    app.add_exception_handler(PlexNotConnected, _unavailable)
    app.add_exception_handler(LLMNotConfigured, _unavailable)

    register_health_routes(app)
    register_setup_routes(app)
    register_config_routes(app)
    register_library_routes(app)
    register_analyze_routes(app)
    register_playlist_routes(app)
    register_recommend_routes(app)
    register_results_routes(app)
    register_art_routes(app)
    # Last: it mounts `/static` and claims the root, so every API path is
    # already registered by the time it could shadow one.
    register_static_routes(app)

    return app
