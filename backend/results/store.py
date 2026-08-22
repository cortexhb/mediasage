"""Reading and writing saved generation results.

Entry points: `save`, `get`, `page`, `remove`. Every function opens its own
session; nothing here is stateful.
"""

import logging
import secrets

from sqlalchemy import delete, func, insert
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from backend.db import db
from backend.results.models import ResultDetail, ResultListItem, ResultListResponse
from backend.results.tables import Result

logger = logging.getLogger(__name__)

# Bytes of randomness in a result id, giving a 16-character hex string.
ID_BYTES = 8

# Attempts before a run of id collisions is treated as a fault.
ID_ATTEMPTS = 10


def save(result: Result) -> str:
    """Store a result under a fresh id and return it.

    Args:
        result: The result to save; its `id` is assigned here

    Returns:
        The id the result was stored under

    Raises:
        RuntimeError: If every generated id collided
    """
    payload = result.model_dump()
    for _ in range(ID_ATTEMPTS):
        result.id = payload["id"] = secrets.token_hex(ID_BYTES)
        try:
            # Core insert, so a collision does not leave an ORM instance detached.
            with db.session() as session:
                session.execute(insert(Result.__table__).values(**payload))
        except IntegrityError:
            continue

        logger.info(
            "Saved result %s (type=%s, tracks=%d)",
            result.id,
            result.type,
            result.track_count,
        )
        return result.id

    raise RuntimeError(f"Failed to generate unique result ID after {ID_ATTEMPTS} attempts")


def get(result_id: str) -> ResultDetail | None:
    """One saved result with its snapshot, or None if it is gone."""
    with db.session() as session:
        row = session.get(Result, result_id)
        return ResultDetail.of(row) if row else None


def page(
    result_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> ResultListResponse:
    """A page of history, newest first, without snapshots.

    Args:
        result_type: Comma-separated types to include; None includes all
        limit: Page size
        offset: Rows to skip

    Returns:
        The page and the total number of results behind it
    """
    types = [t.strip() for t in result_type.split(",") if t.strip()] if result_type else []

    statement = select(Result)
    counter = select(func.count()).select_from(Result)
    if types:
        statement = statement.where(Result.type.in_(types))
        counter = counter.where(Result.type.in_(types))

    statement = statement.order_by(Result.created_at.desc()).limit(limit).offset(offset)

    with db.session() as session:
        total = session.exec(counter).one()
        rows = session.exec(statement).all()
        return ResultListResponse(
            results=[ResultListItem.of(row) for row in rows], total=total
        )


def remove(result_id: str) -> bool:
    """Delete a saved result, reporting whether there was one."""
    with db.session() as session:
        deleted = session.execute(delete(Result).where(Result.id == result_id)).rowcount > 0

    if deleted:
        logger.info("Deleted result %s", result_id)
    return deleted
