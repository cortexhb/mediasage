"""``/api/recommend/analyze-prompt`` -- which filters a prompt implies.

A failure here is not worth blocking on: every filter stays selected and the
user narrows them by hand, so this endpoint has no error path.
"""

import asyncio
import logging
from typing import Annotated

from fastapi import Depends, FastAPI

from backend.models import AnalyzePromptFiltersRequest
from backend.recommender import FilterSuggestion, RecommendationPipeline, pipeline_store

logger = logging.getLogger(__name__)


async def _analyze_prompt(
    request: AnalyzePromptFiltersRequest,
    pipeline: Annotated[RecommendationPipeline | None, Depends(pipeline_store.available)],
) -> FilterSuggestion:
    """``POST /api/recommend/analyze-prompt`` -- which filters a prompt implies.

    A failure here is not worth blocking on: every filter stays selected and
    the user narrows them by hand.
    """

    def everything(reason: str) -> FilterSuggestion:
        return FilterSuggestion(genres=request.genres, decades=request.decades, reasoning=reason)

    if pipeline is None:
        return everything("LLM not configured; returning all filters.")

    try:
        return await asyncio.to_thread(
            pipeline.stages().selection.suggest_filters,
            request.prompt,
            request.genres,
            request.decades,
        )
    except Exception:
        logger.exception("analyze-prompt failed, returning all filters")
        return everything("Analysis failed; returning all filters.")


def register_recommend_filter_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/recommend/analyze-prompt",
        _analyze_prompt,
        methods=["POST"],
        response_model=FilterSuggestion,
        operation_id="analyzeRecommendPrompt",
    )
