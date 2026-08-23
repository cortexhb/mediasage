"""``/api/analyze`` and ``/api/filter/preview`` -- what a prompt implies.

Two resources, and they need different things: analysis needs Plex and a
model, the preview needs neither once the library is cached.

Modules:
    analysis  -- /api/analyze -- a prompt or a seed track, read by a model
    filters   -- /api/filter/preview -- how many tracks match, and its cost
"""

from fastapi import FastAPI

from backend.api.routes.analyze.analysis import Analysis, register_analysis_routes
from backend.api.routes.analyze.filters import register_filter_routes

__all__ = ["Analysis", "register_analyze_routes"]


def register_analyze_routes(app: FastAPI) -> None:
    """Mount both resources, keeping one entry point for `app.py`."""
    register_analysis_routes(app)
    register_filter_routes(app)
