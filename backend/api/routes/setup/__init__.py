"""``/api/setup`` -- the onboarding checklist and what it validates.

The AI endpoint proves a provider works before saving it, so a wrong
credential is a form error rather than something the user discovers on their
first generation. The proving is `backend.api.probes`, shared with
``POST /api/config`` so the two ways into the same settings cannot drift apart.

Modules:
    status      -- /api/setup/status -- the checklist
    ai          -- /api/setup/validate-ai -- prove the provider, then save

There is no Plex counterpart: Plex is configured by signing in, under
`/api/plex`. See `docs/plex_login.md`.
"""

from fastapi import FastAPI

from backend.api.routes.setup.ai import register_validate_ai_routes
from backend.api.routes.setup.status import register_setup_status_routes

__all__ = ["register_setup_routes"]


def register_setup_routes(app: FastAPI) -> None:
    """Mount the checklist, keeping one entry point for `app.py`."""
    register_setup_status_routes(app)
    register_validate_ai_routes(app)
