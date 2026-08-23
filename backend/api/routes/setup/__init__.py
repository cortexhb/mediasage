"""``/api/setup`` -- the onboarding wizard.

Each validate endpoint proves a dependency works before saving it, so a wrong
credential is a form error rather than something the user discovers on their
first generation. Both save on success and rebuild the client they configured.

The proving is `backend.api.probes`, shared with ``POST /api/config`` so the
two ways into the same settings cannot drift apart.

Modules:
    status      -- /api/setup/status -- the checklist, and what came from env
    plex        -- /api/setup/validate-plex -- connect, then save
    ai          -- /api/setup/validate-ai -- one real completion, then save
"""

from fastapi import FastAPI

from backend.api.routes.setup.ai import register_validate_ai_routes
from backend.api.routes.setup.plex import register_validate_plex_routes
from backend.api.routes.setup.status import register_setup_status_routes

__all__ = ["register_setup_routes"]


def register_setup_routes(app: FastAPI) -> None:
    """Mount the wizard, keeping one entry point for `app.py`."""
    register_setup_status_routes(app)
    register_validate_plex_routes(app)
    register_validate_ai_routes(app)
