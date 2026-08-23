"""Reissue saved result ids as uuid4.

Revision ID: 0002_uuid_result_ids
Revises: 0001_orm_schema

`results.id` used to be 16 hex characters from `secrets.token_hex`. The route
now validates the id as a uuid4 before looking it up, so a row keeping its old
id would list in the history and then 400 when opened.

Nothing references `results.id`, so the rows are simply reissued. The old ids
are not recoverable, which is why `downgrade` leaves them alone: they are
opaque either way, and only the application's validator cared about the shape.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_uuid_result_ids"
down_revision: str | None = "0001_orm_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if "results" not in set(sa.inspect(bind).get_table_names()):
        return

    reissued = 0
    for (old,) in bind.execute(sa.text("SELECT id FROM results")).all():
        if _is_uuid(old):
            continue
        bind.execute(
            sa.text("UPDATE results SET id = :new WHERE id = :old"),
            {"new": str(uuid.uuid4()), "old": old},
        )
        reissued += 1

    if reissued:
        op.get_context().impl.static_output(f"Reissued {reissued} result ids as uuid4")


def _is_uuid(value: str) -> bool:
    """Whether an id is already canonical, so a re-run reissues nothing."""
    try:
        return str(uuid.UUID(value)) == value
    except (ValueError, AttributeError, TypeError):
        return False


def downgrade() -> None:
    """No-op: the ids this replaced were random and are not recoverable."""
