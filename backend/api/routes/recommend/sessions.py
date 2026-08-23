"""``/api/recommend/questions`` and ``/api/recommend/switch-mode``.

The session is what carries a round's prompt, questions and answers, and what
its costs land on. Both endpoints here create or replace one.
"""

import asyncio
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from backend.models import (
    RecommendQuestionsRequest,
    RecommendQuestionsResponse,
    RecommendSwitchModeRequest,
    RecommendSwitchModeResponse,
)
from backend.recommender import RecommendationPipeline, RecommendSession, pipeline_store


async def _questions(
    request: RecommendQuestionsRequest,
    pipeline: Annotated[RecommendationPipeline, Depends(pipeline_store.require)],
) -> RecommendQuestionsResponse:
    """``POST /api/recommend/questions`` -- two questions, and a session.

    The session is created before the first call so both calls' costs land on
    it, and deleted again if either fails: a session with no questions in it
    would strand the user on a form with nothing to answer.
    """
    session_id = pipeline.sessions.create(RecommendSession(prompt=request.prompt))
    try:
        dimension_ids = await asyncio.to_thread(
            pipeline.stages(session_id).selection.gap_analysis, request.prompt
        )
        questions = await asyncio.to_thread(
            pipeline.stages(session_id).selection.generate_questions,
            request.prompt, dimension_ids,
        )
    except Exception as err:
        pipeline.sessions.delete(session_id)
        raise HTTPException(
            status_code=500, detail=f"Question generation failed: {err!s}"
        ) from err

    pipeline.sessions.set_questions(session_id, questions)
    tokens, cost = pipeline.sessions.spend(session_id)

    return RecommendQuestionsResponse(
        questions=questions, session_id=session_id, token_count=tokens, estimated_cost=cost
    )


async def _switch_mode(
    request: RecommendSwitchModeRequest,
    pipeline: Annotated[RecommendationPipeline, Depends(pipeline_store.require)],
) -> RecommendSwitchModeResponse:
    """``POST /api/recommend/switch-mode`` -- keep the answers, change the mode.

    A new session rather than an edited one: the candidates the old mode loaded
    do not apply, and generate reloads them for whichever mode asks.
    """
    old = pipeline.sessions.get(request.session_id)
    if not old:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    if request.mode == old.mode:
        return RecommendSwitchModeResponse(session_id=request.session_id)

    switched = pipeline.sessions.create(RecommendSession(
        mode=request.mode,
        prompt=old.prompt,
        filters=old.filters,
        questions=old.questions,
        answers=old.answers,
        familiarity_pref=old.familiarity_pref,
        previously_recommended=old.previously_recommended,
    ))
    pipeline.sessions.delete(request.session_id)
    return RecommendSwitchModeResponse(session_id=switched)


def register_recommend_session_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/recommend/questions", _questions, methods=["POST"],
        response_model=RecommendQuestionsResponse,
    )
    app.add_api_route(
        "/api/recommend/switch-mode", _switch_mode, methods=["POST"],
        response_model=RecommendSwitchModeResponse,
    )
