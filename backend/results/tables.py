"""Table definition for saved generation results.

One row per playlist or album recommendation the app produced, holding the full
response snapshot so history can be re-rendered without calling a model again.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from backend.db.base import Base
from backend.library.tables import UTC_NOW


class Result(Base):
    """A saved playlist or album recommendation.

    `snapshot` is the serialized response the UI renders; the flat columns
    beside it exist so the history list can be built without decoding it.
    """

    __tablename__ = "results"

    # Assigned by `backend.results.store.save`; empty until a row is written.
    id: Mapped[str] = mapped_column(primary_key=True, default="")
    type: Mapped[str]
    title: Mapped[str]
    prompt: Mapped[str]
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    track_count: Mapped[int] = mapped_column(default=0)
    artist: Mapped[str | None] = mapped_column(default=None)
    art_rating_key: Mapped[str | None] = mapped_column(default=None)
    subtitle: Mapped[str | None] = mapped_column(default=None)
    # `UTC_NOW` is aware: a naive Postgres column would shift it by whatever
    # the server's TimeZone happens to be. SQLite stores the same either way.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=UTC_NOW)

    # History reads newest first, filtered by type or not at all. No DESC: both
    # backends scan an index backwards, and an expression index defeats
    # autogenerate, which then reports these as changed on every run.
    __table_args__ = (
        Index("idx_results_type_created", "type", "created_at"),
        Index("idx_results_created_at", "created_at"),
    )

    def payload(self) -> dict[str, Any]:
        """This row's columns, as values a Core insert can be given.

        Columns still unset are left out rather than sent as NULL, so the
        insert applies their defaults -- `created_at` above is one.
        """
        return {
            column.key: value
            for column in self.__table__.columns
            if (value := getattr(self, column.key, None)) is not None
        }

    @staticmethod
    def is_valid_id(result_id: str) -> bool:
        """Whether an id is one `ResultStore.save` could have minted.

        Round-tripped through `str`, because `UUID()` also accepts braces, a
        `urn:` prefix and undashed hex -- none of which the store ever writes.
        """
        try:
            return str(uuid.UUID(result_id)) == result_id
        except ValueError:
            return False
