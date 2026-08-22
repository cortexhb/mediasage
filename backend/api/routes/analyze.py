"""``/api/analyze`` and ``/api/filter/preview`` -- what a prompt implies.

Both analysis endpoints need Plex and a model. The preview needs neither when
the library is cached, which is the point of caching it.
"""

import asyncio
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, HTTPException

from backend import library
from backend.analyzer import analyze_prompt, analyze_track
from backend.api import estimates, guards
from backend.library import TrackFilter
from backend.models import (
    AnalyzePromptRequest,
    AnalyzePromptResponse,
    AnalyzeTrackRequest,
    AnalyzeTrackResponse,
    FilterPreviewRequest,
    FilterPreviewResponse,
)
from backend.plex import PlexFilter, PlexQueryError


async def _analysed(work: Callable[..., Any], *args: Any) -> Any:
    """Run one analysis call, mapping its failures onto status codes.

    A ValueError is the model returning something unusable, which the user can
    act on by rephrasing; anything else is ours and is not shown to them.
    """
    try:
        return await asyncio.to_thread(work, *args)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {err!s}") from err


async def _analyze_prompt(
    request: AnalyzePromptRequest, plex: guards.Plex, llm: guards.LLM
) -> AnalyzePromptResponse:
    """``POST /api/analyze/prompt`` -- which filters a sentence implies.

    `plex` and `llm` are declared for the guards alone: the analyzer reads both
    stores itself, but a missing one must be a 503 rather than a 500.
    """
    return await _analysed(analyze_prompt, request.prompt)


async def _analyze_track(
    request: AnalyzeTrackRequest, plex: guards.Plex, llm: guards.LLM
) -> AnalyzeTrackResponse:
    """``POST /api/analyze/track`` -- the dimensions of a seed track."""
    track = await asyncio.to_thread(plex.track_by_key, request.rating_key)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    return await _analysed(analyze_track, track)


async def _preview_filters(
    request: FilterPreviewRequest, config: guards.Config
) -> FilterPreviewResponse:
    """``POST /api/filter/preview`` -- how many tracks match, and what it costs.

    The cache answers instantly; Plex is the fallback until one exists, and
    only then does this endpoint need a connected server.
    """
    if library.has_tracks():
        matching = await asyncio.to_thread(
            library.tracks.count,
            TrackFilter(
                genres=request.genres or [],
                decades=request.decades or [],
                min_rating=request.min_rating,
                exclude_live=request.exclude_live,
            ),
        )
    else:
        try:
            matching = await asyncio.to_thread(
                guards.require_plex().count,
                PlexFilter(
                    genres=request.genres or [],
                    decades=request.decades or [],
                    min_rating=request.min_rating,
                    exclude_live=request.exclude_live,
                ),
            )
        except PlexQueryError as err:
            raise HTTPException(status_code=502, detail=str(err)) from err

    return estimates.playlist(request, matching, config)


def register_analyze_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/analyze/prompt", _analyze_prompt, methods=["POST"],
        response_model=AnalyzePromptResponse,
    )
    app.add_api_route(
        "/api/analyze/track", _analyze_track, methods=["POST"],
        response_model=AnalyzeTrackResponse,
    )
    app.add_api_route(
        "/api/filter/preview", _preview_filters, methods=["POST"],
        response_model=FilterPreviewResponse,
    )
