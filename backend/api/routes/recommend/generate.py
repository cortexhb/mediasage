"""``/api/recommend/generate`` -- one round, streamed.

`RecommendationRound` does the generating; this module resolves what it needs
before the stream opens and streams what it reports.
"""

import asyncio
import logging
import random
from collections.abc import AsyncIterator
from typing import Annotated, Final

from fastapi import Depends, FastAPI, HTTPException, Request
from starlette.responses import StreamingResponse

from backend import library
from backend.api.clients import shared
from backend.library import AlbumCandidate, TrackFilter
from backend.models import RecommendGenerateRequest
from backend.recommender import (
    AnswerSet,
    RecommendationPipeline,
    TasteProfile,
    pipeline_store,
)
from backend.recommender.round import RecommendationRound, RoundInputs, Step
from backend.sse import SSE

logger = logging.getLogger(__name__)

# Why a library round has nothing to recommend from. Each says what to do next.
EMPTY_LIBRARY: Final = "Library cache is empty. Please sync your library first."
EMPTY_FOR_DISCOVERY: Final = (
    "Library cache is empty. Discovery mode needs your library to build a taste "
    "profile. Please sync first."
)
SYNC_RUNNING: Final = (
    "Library sync in progress. Album recommendations will be available once it completes."
)
NEEDS_RESYNC: Final = (
    "Your library needs a fresh sync to enable album recommendations. "
    "Please re-sync from Settings or the footer Refresh link."
)

# iOS Safari tears down the connection of a backgrounded tab even when the user
# means to come back, so a disconnect there is not a cancellation.
IOS_AGENTS: Final = ("iphone", "ipad")


async def _load_candidates(
    request: RecommendGenerateRequest,
) -> tuple[list[AlbumCandidate], TasteProfile]:
    """The albums a round chooses from, and the profile discovery needs.

    Raises:
        HTTPException: When the cache cannot answer, saying which sync to run
    """
    if not library.library_sync.has_tracks():
        raise HTTPException(
            status_code=400,
            detail=EMPTY_FOR_DISCOVERY if request.mode == "discovery" else EMPTY_LIBRARY,
        )

    library_mode = request.mode == "library"
    candidates = await asyncio.to_thread(
        library.album_cache.candidates,
        TrackFilter(
            genres=request.genres if library_mode else [],
            decades=request.decades if library_mode else [],
        ),
    )

    if library_mode and not candidates:
        if library.library_sync.status().is_syncing:
            raise HTTPException(status_code=409, detail=SYNC_RUNNING)
        raise HTTPException(status_code=400, detail=NEEDS_RESYNC)

    # Sampled rather than truncated: taking the first N would bias every round
    # towards whichever albums the cache happens to return first.
    if 0 < request.max_albums < len(candidates):
        candidates = random.sample(candidates, request.max_albums)

    profile = TasteProfile()
    if request.mode == "discovery":
        owned = await asyncio.to_thread(library.album_cache.candidates, TrackFilter())
        profile = TasteProfile.of(owned)

    return candidates, profile


async def _generate(
    request: RecommendGenerateRequest, raw_request: Request,
    pipeline: Annotated[RecommendationPipeline, Depends(pipeline_store.require)],
) -> StreamingResponse:
    """``POST /api/recommend/generate`` -- one round, streamed.

    Everything the round reads is resolved here, before the stream opens: a
    concurrent "Show me another" on the same session would otherwise mutate it
    mid-round, and a validation failure is better as a status code than as an
    error frame.
    """
    session = pipeline.sessions.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    answers = AnswerSet(answers=request.answers, texts=request.answer_texts)
    pipeline.sessions.set_answers(request.session_id, answers)

    candidates, profile = await _load_candidates(request)
    pipeline.sessions.start_round(
        request.session_id,
        mode=request.mode,
        filters={"genres": request.genres, "decades": request.decades},
        familiarity_pref=request.familiarity_pref,
        album_candidates=candidates,
    )

    inputs = RoundInputs(
        session_id=request.session_id,
        prompt=session.prompt,
        mode=request.mode,
        answers=answers,
        familiarity_pref=request.familiarity_pref,
        candidates=candidates,
        profile=profile,
        already_shown=list(session.previously_recommended),
        max_exclusion_albums=request.max_albums,
    )

    agent = (raw_request.headers.get("user-agent") or "").lower()
    is_ios = any(name in agent for name in IOS_AGENTS)

    async def abandoned() -> bool:
        """Whether to stop spending because the caller has gone."""
        if is_ios:
            return False
        if await raw_request.is_disconnected():
            logger.info("Client disconnected, aborting session %s", request.session_id)
            return True
        return False

    round_ = RecommendationRound(pipeline, shared.research(), inputs, abandoned)

    async def events() -> AsyncIterator[str]:
        try:
            async for update in round_.run():
                if isinstance(update, Step):
                    yield SSE.progress(update.step, update.message)
                    continue

                payload = update.model_dump(mode="json")
                result_id = await asyncio.to_thread(round_.save, update)
                if result_id:
                    payload["result_id"] = result_id

                yield SSE.result(payload)
                pipeline.sessions.remember(
                    request.session_id, [rec.ref for rec in update.recommendations]
                )
        except ValueError as err:
            # Written for the user; anything else is ours and is not shown.
            yield SSE.error(str(err))
        except Exception:
            logger.exception("Recommendation generation failed")
            yield SSE.error(
                "An error occurred during recommendation generation. Please try again."
            )

    return SSE.serve(events())


def register_recommend_generate_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/recommend/generate", _generate, methods=["POST"], response_model=None
    )
