"""``GET /api/health`` -- is the application wired up.

Answers without touching Plex or a model: both are reported from the state the
stores already hold, so a health check never waits on a network round trip.
"""

from typing import Annotated

from fastapi import Depends, FastAPI

from backend.config import MediasageConfig, config_store
from backend.models import HealthResponse
from backend.plex import plex_store


async def _health(
    config: Annotated[MediasageConfig, Depends(config_store.get)],
    plex_connected: Annotated[bool, Depends(plex_store.is_connected)],
) -> HealthResponse:
    """``GET /api/health`` -- connectivity of both dependencies."""
    return HealthResponse(
        status="healthy",
        plex_connected=plex_connected,
        llm_configured=config.llm.is_configured,
    )


def register_health_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/health", _health, methods=["GET"], response_model=HealthResponse
    )
