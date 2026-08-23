"""``/api/analyze`` -- what a prompt or a seed track implies.

Both endpoints need Plex and a model. `Analysis` owns the synchronous
`Analyzer` off the event loop, and the status code each failure becomes.
"""

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from backend.analyzer import Analyzer
from backend.llm import LLMClient, client_store
from backend.models import (
    AnalyzePromptRequest,
    AnalyzePromptResponse,
    AnalyzeTrackRequest,
    AnalyzeTrackResponse,
    Track,
)
from backend.plex import PlexClient, plex_store


class Analysis:
    """One analyzer, awaited off the event loop and answered in status codes.

    Here rather than on `Analyzer`: `HTTPException` is FastAPI's, and no
    package below `backend.api` imports the framework. A plain class rather
    than a model: it holds a collaborator, not data to validate.
    """

    def __init__(self, analyzer: Analyzer) -> None:
        self.analyzer = analyzer

    async def of_prompt(self, prompt: str) -> AnalyzePromptResponse:
        """The filters a sentence implies."""
        with self._mapped():
            return await asyncio.to_thread(self.analyzer.analyze_prompt, prompt)

    async def of_track(self, track: Track) -> AnalyzeTrackResponse:
        """The dimensions a seed track can be explored along."""
        with self._mapped():
            return await asyncio.to_thread(self.analyzer.analyze_track, track)

    @contextmanager
    def _mapped(self) -> Generator[None]:
        """Turn one analysis failure into the status code it deserves.

        A ValueError is the model returning something unusable, which the user
        can act on by rephrasing; anything else is ours and is not shown.
        """
        try:
            yield
        except ValueError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        except Exception as err:
            raise HTTPException(status_code=500, detail=f"Analysis failed: {err!s}") from err


async def _analyze_prompt(
    request: AnalyzePromptRequest,
    plex: Annotated[PlexClient, Depends(plex_store.require)],
    llm: Annotated[LLMClient, Depends(client_store.require)],
) -> AnalyzePromptResponse:
    """``POST /api/analyze/prompt`` -- which filters a sentence implies."""
    return await Analysis(Analyzer(llm=llm, plex=plex)).of_prompt(request.prompt)


async def _analyze_track(
    request: AnalyzeTrackRequest,
    plex: Annotated[PlexClient, Depends(plex_store.require)],
    llm: Annotated[LLMClient, Depends(client_store.require)],
) -> AnalyzeTrackResponse:
    """``POST /api/analyze/track`` -- the dimensions of a seed track."""
    track = await asyncio.to_thread(plex.library.track_by_key, request.rating_key)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    return await Analysis(Analyzer(llm=llm, plex=plex)).of_track(track)


def register_analysis_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/analyze/prompt",
        _analyze_prompt,
        methods=["POST"],
        response_model=AnalyzePromptResponse,
        operation_id="analyzePrompt",
    )
    app.add_api_route(
        "/api/analyze/track",
        _analyze_track,
        methods=["POST"],
        response_model=AnalyzeTrackResponse,
        operation_id="analyzeTrack",
    )
