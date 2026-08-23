"""Reading and writing saved generation results.

`ResultStore` is the whole surface; `results_store` is the instance the
application talks through, matching how the config, Plex, LLM and pipeline
stores are reached. It holds nothing: every call opens its own session, so
there is no connection to keep alive or invalidate.
"""

import logging
import uuid

from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError

from backend.db import db
from backend.results.models import ResultListItem, ResultListResponse, SavedResult
from backend.results.tables import Result

logger = logging.getLogger(__name__)

# Attempts before a run of id collisions is treated as a fault.
ID_ATTEMPTS = 10


class ResultStore:
    """The saved history, as rows go in and come back out.

    A plain class, not a model: it carries no fields, and every call opens and
    closes its own session.
    """

    def save(self, result: Result) -> str:
        """Store a result under a fresh id and return it.

        Args:
            result: The result to save; its `id` is assigned here

        Returns:
            The id the result was stored under

        Raises:
            RuntimeError: If every generated id collided
        """
        payload = result.payload()
        for _ in range(ID_ATTEMPTS):
            result.id = payload["id"] = str(uuid.uuid4())
            try:
                # Values, not the instance: a collision must not detach an ORM row.
                with db.session() as session:
                    session.execute(insert(Result).values(**payload))
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

    def get(self, result_id: str) -> SavedResult | None:
        """One saved result with its snapshot, or None if it is gone."""
        with db.session() as session:
            row = session.get(Result, result_id)
            return SavedResult.of(row) if row else None

    def page(
        self,
        result_type: str = "",
        limit: int = 20,
        offset: int = 0,
    ) -> ResultListResponse:
        """A page of history, newest first, without snapshots.

        Args:
            result_type: Comma-separated types to include; empty includes all
            limit: Page size
            offset: Rows to skip

        Returns:
            The page and the total number of results behind it
        """
        types = [t.strip() for t in result_type.split(",") if t.strip()]

        statement = select(Result)
        counter = select(func.count()).select_from(Result)
        if types:
            statement = statement.where(Result.type.in_(types))
            counter = counter.where(Result.type.in_(types))

        statement = statement.order_by(Result.created_at.desc()).limit(limit).offset(offset)

        with db.session() as session:
            total = session.execute(counter).scalar_one()
            rows = session.scalars(statement).all()
            return ResultListResponse(results=[ResultListItem.of(row) for row in rows], total=total)

    def remove(self, result_id: str) -> bool:
        """Delete a saved result, reporting whether there was one."""
        with db.session() as session:
            # Through the connection: only a cursor result is typed to count rows.
            cursor = session.connection().execute(delete(Result).where(Result.id == result_id))
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info("Deleted result %s", result_id)
        return deleted


# The single instance the application talks through.
results_store = ResultStore()
