"""``/api/results/{result_id}`` -- reading and forgetting one result.

Result ids are uuid4, so anything else is rejected before it reaches the store
rather than being looked up and missed. `Result.is_valid_id` owns that shape.
"""

import asyncio
from typing import Final

from fastapi import FastAPI, HTTPException, Response

from backend.results import Result, ResultDetail, results_store

# Refused before the store is asked, so never a lookup miss.
BAD_ID: Final = "Invalid result ID format"


async def _get_result(result_id: str) -> ResultDetail:
    """``GET /api/results/{result_id}`` -- one result with its full snapshot."""
    if not Result.is_valid_id(result_id):
        raise HTTPException(status_code=400, detail=BAD_ID)

    result = await asyncio.to_thread(results_store.get, result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result


async def _delete_result(result_id: str) -> Response:
    """``DELETE /api/results/{result_id}`` -- forget one result."""
    if not Result.is_valid_id(result_id):
        raise HTTPException(status_code=400, detail=BAD_ID)

    if not await asyncio.to_thread(results_store.remove, result_id):
        raise HTTPException(status_code=404, detail="Result not found")
    return Response(status_code=204)


def register_detail_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/results/{result_id}", _get_result, methods=["GET"], response_model=ResultDetail
    )
    app.add_api_route(
        "/api/results/{result_id}", _delete_result, methods=["DELETE"],
        status_code=204, response_model=None,
    )
