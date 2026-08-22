"""``GET /api/health`` -- is the application wired up.

Answers without touching Plex or a model: both are reported from the state the
stores already hold, so a health check never waits on a network round trip.
"""

from fastapi import FastAPI

from backend.api import guards
from backend.models import HealthResponse


async def _health(config: guards.Config) -> HealthResponse:
    """``GET /api/health`` -- connectivity of both dependencies."""
    return HealthResponse(
        status="healthy",
        plex_connected=guards.plex_client() is not None,
        llm_configured=guards.llm_is_configured(config),
    )


def register_health_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/health", _health, methods=["GET"], response_model=HealthResponse
    )
