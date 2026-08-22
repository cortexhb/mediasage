"""``/api/results`` -- the saved history of playlists and recommendations.

Result ids are generated hex, so anything else is rejected before it reaches
the store rather than being looked up and missed.
"""

import asyncio
import re
from typing import Final

from fastapi import FastAPI, HTTPException, Query, Response

from backend.results import ResultDetail, ResultListResponse
from backend.results import store as results_store

# What the history view can hold. A type outside this set is a client bug, not
# an empty page.
VALID_TYPES: Final = frozenset({"prompt_playlist", "seed_playlist", "album_recommendation"})

# The shape `results_store` mints. Checked before a lookup so a malformed id is
# a 400 rather than a 404.
RESULT_ID: Final = re.compile(r"^[0-9a-f]{8,16}$")


def _checked_id(result_id: str) -> str:
    """The id, or a 400 if it is not one we could have issued."""
    if not RESULT_ID.match(result_id):
        raise HTTPException(status_code=400, detail="Invalid result ID format")
    return result_id


async def _list_results(
    type: str | None = Query(None, description="Filter by type (comma-separated)"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ResultListResponse:
    """``GET /api/results`` -- one page of saved results."""
    if type:
        unknown = {name.strip() for name in type.split(",")} - VALID_TYPES
        if unknown:
            raise HTTPException(
                status_code=400, detail=f"Invalid result type: {', '.join(sorted(unknown))}"
            )
    return await asyncio.to_thread(
        results_store.page, result_type=type, limit=limit, offset=offset
    )


async def _get_result(result_id: str) -> ResultDetail:
    """``GET /api/results/{result_id}`` -- one result with its full snapshot."""
    result = await asyncio.to_thread(results_store.get, _checked_id(result_id))
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result


async def _delete_result(result_id: str) -> Response:
    """``DELETE /api/results/{result_id}`` -- forget one result."""
    if not await asyncio.to_thread(results_store.remove, _checked_id(result_id)):
        raise HTTPException(status_code=404, detail="Result not found")
    return Response(status_code=204)


def register_results_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/results", _list_results, methods=["GET"], response_model=ResultListResponse
    )
    app.add_api_route(
        "/api/results/{result_id}", _get_result, methods=["GET"], response_model=ResultDetail
    )
    app.add_api_route(
        "/api/results/{result_id}", _delete_result, methods=["DELETE"],
        status_code=204, response_model=None,
    )
