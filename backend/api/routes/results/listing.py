"""``GET /api/results`` -- one page of saved history."""

import asyncio
from typing import Final

from fastapi import FastAPI, HTTPException, Query

from backend.results import ResultListResponse, results_store

# A type outside this set is a client bug.
VALID_TYPES: Final = frozenset({"prompt_playlist", "seed_playlist", "album_recommendation"})


async def _list_results(
    type: str = Query("", description="Filter by type (comma-separated)"),
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


def register_listing_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/results", _list_results, methods=["GET"], response_model=ResultListResponse
    )
