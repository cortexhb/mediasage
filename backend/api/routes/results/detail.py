"""``/api/results/{result_id}`` -- reading and forgetting one result.

Result ids are uuid4, so anything else is rejected before it reaches the store
rather than being looked up and missed. `Result.is_valid_id` owns that shape.

The stored snapshot is narrowed here, not in the store: it is the response
contract, and its two shapes are only assembled together in `backend.models`.
"""

import asyncio
import logging
from typing import Final

from fastapi import FastAPI, HTTPException, Response
from pydantic import ValidationError

from backend.models import RESULT_DETAIL_ADAPTER, ResultDetail
from backend.results import Result, results_store

logger = logging.getLogger(__name__)

# Refused before the store is asked, so never a lookup miss.
BAD_ID: Final = "Invalid result ID format"

# A snapshot the models cannot parse is one the UI cannot draw.
UNRENDERABLE: Final = "This result was saved by an earlier version and can no longer be shown"


async def _get_result(result_id: str) -> ResultDetail:
    """``GET /api/results/{result_id}`` -- one result with its full snapshot."""
    if not Result.is_valid_id(result_id):
        raise HTTPException(status_code=400, detail=BAD_ID)

    saved = await asyncio.to_thread(results_store.get, result_id)
    if not saved:
        raise HTTPException(status_code=404, detail="Result not found")

    try:
        return RESULT_DETAIL_ADAPTER.validate_python(saved.model_dump())
    except ValidationError as err:
        logger.warning("Result %s no longer validates: %s", result_id, err)
        raise HTTPException(status_code=422, detail=UNRENDERABLE) from err


async def _delete_result(result_id: str) -> Response:
    """``DELETE /api/results/{result_id}`` -- forget one result."""
    if not Result.is_valid_id(result_id):
        raise HTTPException(status_code=400, detail=BAD_ID)

    if not await asyncio.to_thread(results_store.remove, result_id):
        raise HTTPException(status_code=404, detail="Result not found")
    return Response(status_code=204)


def register_detail_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/results/{result_id}",
        _get_result,
        methods=["GET"],
        response_model=ResultDetail,
        operation_id="getResult",
    )
    app.add_api_route(
        "/api/results/{result_id}",
        _delete_result,
        methods=["DELETE"],
        status_code=204,
        response_model=None,
        operation_id="deleteResult",
    )
