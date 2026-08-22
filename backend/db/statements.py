"""Statements whose SQL differs between backends.

Everything else in the codebase builds portable SQLAlchemy expressions. This is
the one module that knows dialect names, so a Postgres move touches it and the
engine and nothing else. Entry point: `upsert`.
"""

from typing import Any

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Dialect
from sqlalchemy.sql import Executable

# Backends whose INSERT supports ON CONFLICT with the same builder shape.
UPSERT_DIALECTS = {"sqlite": sqlite_insert, "postgresql": postgres_insert}


def upsert(
    dialect: Dialect, table: Table, rows: list[dict[str, Any]], keys: list[str]
) -> Executable:
    """Insert `rows`, overwriting the non-key columns of any that already exist.

    Args:
        dialect: The engine's dialect, deciding which INSERT builder applies
        table: Target table
        rows: Column-keyed values; every row must carry the same columns
        keys: Columns forming the conflict target, usually the primary key

    Returns:
        An executable INSERT … ON CONFLICT DO UPDATE statement

    Raises:
        NotImplementedError: If the backend has no supported upsert form
        ValueError: If `rows` is empty
    """
    if not rows:
        raise ValueError("upsert needs at least one row")

    builder = UPSERT_DIALECTS.get(dialect.name)
    if builder is None:
        raise NotImplementedError(f"No upsert form for dialect {dialect.name!r}")

    statement = builder(table).values(rows)
    updates = {
        column: statement.excluded[column] for column in rows[0] if column not in keys
    }
    return statement.on_conflict_do_update(index_elements=keys, set_=updates)
