"""``/api/config`` and ``/api/ollama`` -- settings, and what fills them in.

Ollama's endpoints are here rather than beside the other providers because
they exist to fill the settings form: they answer about a URL the user is
still typing, not about the configured one.

Modules:
    settings  -- /api/config -- read settings, prove a change, publish it
    ollama    -- /api/ollama -- what a local server has, for the form
"""

from fastapi import FastAPI

from backend.api.routes.config.ollama import register_ollama_routes
from backend.api.routes.config.settings import register_settings_routes

__all__ = ["register_config_routes"]


def register_config_routes(app: FastAPI) -> None:
    """Mount both resources, keeping one entry point for `app.py`."""
    register_settings_routes(app)
    register_ollama_routes(app)
