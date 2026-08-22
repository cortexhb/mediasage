"""``/api/recommend`` -- album recommendations, questions first.

The flow is four requests: preview what a round would cost, ask the user two
clarifying questions, then generate. `RecommendationRound` does the generating;
this module resolves what it needs and streams what it reports.
"""

import asyncio
import logging
import random

from fastapi import FastAPI, HTTPException, Query, Request
from starlette.responses import StreamingResponse

from backend import library
from backend.api import clients, estimates, guards, sse
from backend.library import TrackFilter
from backend.models import (
    AlbumPreviewResponse,
    AnalyzePromptFiltersRequest,
    RecommendGenerateRequest,
    RecommendQuestionsRequest,
    RecommendQuestionsResponse,
    RecommendSwitchModeRequest,
    RecommendSwitchModeResponse,
)
from backend.recommender import (
    AnswerSet,
    FilterSuggestion,
    RecommendSession,
    TasteProfile,
)
from backend.recommender.round import RecommendationRound, RoundInputs, Step
from backend.results import Result
from backend.results import store as results_store

logger = logging.getLogger(__name__)

# Why a library round has nothing to recommend from. Each says what to do next.
EMPTY_LIBRARY = "Library cache is empty. Please sync your library first."
EMPTY_FOR_DISCOVERY = (
    "Library cache is empty. Discovery mode needs your library to build a taste "
    "profile. Please sync first."
)
SYNC_RUNNING = (
    "Library sync in progress. Album recommendations will be available once it completes."
)
NEEDS_RESYNC = (
    "Your library needs a fresh sync to enable album recommendations. "
    "Please re-sync from Settings or the footer Refresh link."
)

# iOS Safari tears down the connection of a backgrounded tab even when the user
# means to come back, so a disconnect there is not a cancellation.
IOS_AGENTS = ("iphone", "ipad")


def _split(value: str | None) -> list[str]:
    """A comma-separated query parameter as a list, blanks dropped."""
    return [part.strip() for part in value.split(",") if part.strip()] if value else []


async def _preview(
    config: guards.Config,
    genres: str | None = Query(None, description="Comma-separated genre names"),
    decades: str | None = Query(None, description="Comma-separated decade names"),
    max_albums: int = Query(2500, description="Max albums to send to AI"),
) -> AlbumPreviewResponse:
    """``GET /api/recommend/albums/preview`` -- what a round would cost."""
    matching = 0
    if library.has_tracks():
        candidates = await asyncio.to_thread(
            library.albums.candidates,
            TrackFilter(genres=_split(genres), decades=_split(decades)),
        )
        matching = len(candidates)

    return estimates.albums(matching, max_albums, config)


async def _analyze_prompt(request: AnalyzePromptFiltersRequest) -> FilterSuggestion:
    """``POST /api/recommend/analyze-prompt`` -- which filters a prompt implies.

    A failure here is not worth blocking on: every filter stays selected and
    the user narrows them by hand.
    """
    def everything(reason: str) -> FilterSuggestion:
        return FilterSuggestion(
            genres=request.genres, decades=request.decades, reasoning=reason
        )

    pipeline = guards.pipeline()
    if pipeline is None:
        return everything("LLM not configured; returning all filters.")

    try:
        return await asyncio.to_thread(
            pipeline.suggest_filters, request.prompt, request.genres, request.decades
        )
    except Exception:
        logger.exception("analyze-prompt failed, returning all filters")
        return everything("Analysis failed; returning all filters.")


async def _questions(
    request: RecommendQuestionsRequest, pipeline: guards.Pipeline
) -> RecommendQuestionsResponse:
    """``POST /api/recommend/questions`` -- two questions, and a session.

    The session is created before the first call so both calls' costs land on
    it, and deleted again if either fails: a session with no questions in it
    would strand the user on a form with nothing to answer.
    """
    session_id = pipeline.sessions.create(RecommendSession(prompt=request.prompt))
    try:
        dimension_ids = await asyncio.to_thread(
            pipeline.gap_analysis, session_id, request.prompt
        )
        questions = await asyncio.to_thread(
            pipeline.generate_questions, session_id, request.prompt, dimension_ids
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
    request: RecommendSwitchModeRequest, pipeline: guards.Pipeline
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


async def _load_candidates(request: RecommendGenerateRequest):
    """The albums a round chooses from, and the profile discovery needs.

    Raises:
        HTTPException: When the cache cannot answer, saying which sync to run
    """
    if not library.has_tracks():
        raise HTTPException(
            status_code=400,
            detail=EMPTY_FOR_DISCOVERY if request.mode == "discovery" else EMPTY_LIBRARY,
        )

    library_mode = request.mode == "library"
    candidates = await asyncio.to_thread(
        library.albums.candidates,
        TrackFilter(
            genres=request.genres if library_mode else [],
            decades=request.decades if library_mode else [],
        ),
    )

    if library_mode and not candidates:
        if library.sync_status().is_syncing:
            raise HTTPException(status_code=409, detail=SYNC_RUNNING)
        raise HTTPException(status_code=400, detail=NEEDS_RESYNC)

    # Sampled rather than truncated: taking the first N would bias every round
    # towards whichever albums the cache happens to return first.
    if 0 < request.max_albums < len(candidates):
        candidates = random.sample(candidates, request.max_albums)

    profile = None
    if request.mode == "discovery":
        owned = await asyncio.to_thread(library.albums.candidates, TrackFilter())
        profile = TasteProfile.of(owned)

    return candidates, profile


def _saved(recommendations, prompt: str, result) -> Result:
    """The round's result as a history entry, titled by the primary pick."""
    primary = next((rec for rec in recommendations if rec.rank == "primary"), None)
    return Result(
        type="album_recommendation",
        title=f"{primary.album} by {primary.artist}" if primary else "Album Recommendation",
        prompt=prompt,
        snapshot=result.model_dump(mode="json"),
        track_count=len(recommendations),
        artist=primary.artist if primary else None,
        art_rating_key=(
            primary.track_rating_keys[0]
            if primary and primary.track_rating_keys
            else None
        ),
        subtitle=(primary.pitch.hook if primary and primary.pitch.hook else prompt),
    )


async def _generate(
    request: RecommendGenerateRequest, raw_request: Request, pipeline: guards.Pipeline
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
        taste_profile=profile,
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
        max_exclusion_albums=request.max_albums or None,
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

    round_ = RecommendationRound(pipeline, clients.research(), inputs, abandoned)

    async def events():
        try:
            async for update in round_.run():
                if isinstance(update, Step):
                    yield sse.progress(update.step, update.message)
                    continue

                payload = update.model_dump(mode="json")
                try:
                    result_id = await asyncio.to_thread(
                        results_store.save,
                        _saved(update.recommendations, inputs.prompt, update),
                    )
                    payload["result_id"] = result_id
                except Exception as err:
                    logger.warning("Failed to save recommendation result: %s", err)

                yield sse.result(payload)
                pipeline.sessions.remember(
                    request.session_id, [rec.ref for rec in update.recommendations]
                )
        except ValueError as err:
            # Written for the user; anything else is ours and is not shown.
            yield sse.error(str(err))
        except Exception:
            logger.exception("Recommendation generation failed")
            yield sse.error(
                "An error occurred during recommendation generation. Please try again."
            )

    return sse.stream(events())


def register_recommend_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/recommend/albums/preview", _preview, methods=["GET"],
        response_model=AlbumPreviewResponse,
    )
    app.add_api_route(
        "/api/recommend/analyze-prompt", _analyze_prompt, methods=["POST"],
        response_model=FilterSuggestion,
    )
    app.add_api_route(
        "/api/recommend/questions", _questions, methods=["POST"],
        response_model=RecommendQuestionsResponse,
    )
    app.add_api_route(
        "/api/recommend/switch-mode", _switch_mode, methods=["POST"],
        response_model=RecommendSwitchModeResponse,
    )
    app.add_api_route(
        "/api/recommend/generate", _generate, methods=["POST"], response_model=None
    )
