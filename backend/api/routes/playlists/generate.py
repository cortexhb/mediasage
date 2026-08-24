"""``/api/generate`` -- a playlist, with progress.

Streams because it makes several LLM calls and the user is watching. The seed
track is resolved before the stream opens, so a bad rating key is a 404 rather
than an error frame the user has to read.
"""

import asyncio
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from starlette.responses import StreamingResponse

from backend.api.watching import watch_stream
from backend.generator import PlaylistGeneration
from backend.llm import LLMClient, client_store
from backend.models import GenerateRequest, PlaylistStreamFrame
from backend.plex import PlexClient, plex_store
from backend.sse import SSE, EventStreamResponse


async def _generate(
    request: GenerateRequest,
    plex: Annotated[PlexClient, Depends(plex_store.require)],
    llm: Annotated[LLMClient, Depends(client_store.require)],
) -> StreamingResponse:
    """``POST /api/generate/stream`` -- a playlist, with progress.

    The seed track is resolved before the stream opens, so a bad rating key is
    a 404 rather than an error frame the user has to read.
    """
    seed_track = None
    selected_dimensions = []
    if request.seed_track:
        seed_track = await asyncio.to_thread(
            plex.library.track_by_key, request.seed_track.rating_key
        )
        if not seed_track:
            raise HTTPException(status_code=404, detail="Seed track not found")
        selected_dimensions = request.seed_track.selected_dimensions

    generation = PlaylistGeneration(
        prompt=request.prompt,
        seed_track=seed_track,
        selected_dimensions=selected_dimensions,
        additional_notes=request.additional_notes,
        refinement_answers=request.refinement_answers,
        genres=request.genres,
        decades=request.decades,
        track_count=request.track_count,
        exclude_live=request.exclude_live,
        min_rating=request.min_rating,
        max_tracks_to_ai=request.max_tracks_to_ai,
        flow_id=request.flow_id,
    )
    return SSE.serve(generation.stream())


def register_generate_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/generate/stream",
        _generate,
        methods=["POST"],
        # The body is a stream of frames, which no `response_model` can
        # describe; `responses` puts the frames themselves in the schema.
        response_model=None,
        response_class=EventStreamResponse,
        responses={
            200: {
                "model": PlaylistStreamFrame,
                "description": (
                    "`progress` frames, then `narrative`, `tracks` batches and "
                    "`complete`, or `error`."
                ),
            }
        },
        operation_id="generatePlaylist",
        dependencies=[Depends(watch_stream)],
    )
