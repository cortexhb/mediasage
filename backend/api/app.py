"""Assemble the MediaSage FastAPI application.

`create_app()` is the whole entry point: it builds the app and mounts each
route module in turn. A factory rather than a module-scope `app` so nothing is
read from the config singleton at import time, and so a test can build a fresh
application without the one the process already holds.

Startup and shutdown live in `lifespan`: both clients are built from whatever
is configured, and the schema is brought to head before anything reads it.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api import clients, guards
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
from backend.db import upgrade_to_head
from backend.version import get_version

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build what is configured, then release it on the way out."""
    config = config_store.get()

    if config.plex.url and config.plex.token:
        guards.init_plex(config.plex)

    # A local provider is reached by URL and needs no key.
    if config.llm.api_key or config.llm.is_local:
        guards.init_llm(config.llm)

    # Before anything reads or writes a row.
    upgrade_to_head()

    yield

    await clients.close()


def create_app() -> FastAPI:
    """Build the application and mount every route on it."""
    app = FastAPI(
        title="MediaSage",
        description="Plex playlist generator powered by LLMs",
        version=get_version(),
        lifespan=lifespan,
    )

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
