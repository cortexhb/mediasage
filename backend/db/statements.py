"""Statements whose SQL differs between backends.

Everything else in the codebase builds portable SQLAlchemy expressions. This is
the one module that knows dialect names, so a Postgres move touches it and the
engine and nothing else. Entry point: `Upsert`.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Dialect
from sqlalchemy.sql.dml import Insert

# Backends whose INSERT supports ON CONFLICT with the same builder shape.
UPSERT_DIALECTS = {"sqlite": sqlite_insert, "postgresql": postgres_insert}


class Upsert(BaseModel):
    """Rows to insert, overwriting the non-key columns of any that exist.

    Built once and rendered per dialect: the caller holds the rows, the engine
    decides the SQL. Entry point: `statement`.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    table: Table
    rows: list[dict[str, Any]]
    keys: list[str]

    @field_validator("rows")
    @classmethod
    def _reject_empty(cls, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Pydantic shape: an empty upsert is a caller bug, not an empty write."""
        if not rows:
            raise ValueError("upsert needs at least one row")
        return rows

    def statement(self, dialect: Dialect) -> Insert:
        """The INSERT … ON CONFLICT DO UPDATE this backend understands.

        Args:
            dialect: The engine's dialect, deciding which INSERT builder applies

        Returns:
            The dialect's INSERT; every row must carry the same columns

        Raises:
            NotImplementedError: If the backend has no supported upsert form
        """
        builder = UPSERT_DIALECTS.get(dialect.name)
        if builder is None:
            raise NotImplementedError(f"No upsert form for dialect {dialect.name!r}")

        statement = builder(self.table).values(self.rows)
        updates = {
            column: statement.excluded[column] for column in self.rows[0] if column not in self.keys
        }
        return statement.on_conflict_do_update(index_elements=self.keys, set_=updates)
