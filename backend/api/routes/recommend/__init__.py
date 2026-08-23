"""``/api/recommend`` -- album recommendations, questions first.

The flow is four requests: preview what a round would cost, have a prompt
narrowed to filters, answer two clarifying questions, then generate.

Modules:
    preview   -- /api/recommend/albums/preview -- what a round would cost
    filters   -- /api/recommend/analyze-prompt -- filters a prompt implies
    sessions  -- /api/recommend/questions, /switch-mode -- the session
    generate  -- /api/recommend/generate -- one round, streamed
"""

from fastapi import FastAPI

from backend.api.routes.recommend.filters import register_recommend_filter_routes
from backend.api.routes.recommend.generate import register_recommend_generate_routes
from backend.api.routes.recommend.preview import register_preview_routes
from backend.api.routes.recommend.sessions import register_recommend_session_routes

__all__ = ["register_recommend_routes"]


def register_recommend_routes(app: FastAPI) -> None:
    """Mount the whole flow, keeping one entry point for `app.py`."""
    register_preview_routes(app)
    register_recommend_filter_routes(app)
    register_recommend_session_routes(app)
    register_recommend_generate_routes(app)
