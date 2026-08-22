"""Table definition for saved generation results.

One row per playlist or album recommendation the app produced, holding the full
response snapshot so history can be re-rendered without calling a model again.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import Column, Index
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

from backend.library.tables import utc_now


class Result(SQLModel, table=True):
    """A saved playlist or album recommendation.

    `snapshot` is the serialized response the UI renders; the flat columns
    beside it exist so the history list can be built without decoding it.
    """

    __tablename__ = "results"

    # Assigned by `backend.results.store.save`; empty until a row is written.
    id: str = Field(default="", primary_key=True)
    type: str
    title: str
    prompt: str
    snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    track_count: int = 0
    artist: str | None = None
    art_rating_key: str | None = None
    subtitle: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    # History reads newest first, filtered by type or not at all. No DESC: both
    # backends scan an index backwards, and an expression index defeats
    # autogenerate, which then reports these as changed on every run.
    __table_args__ = (
        Index("idx_results_type_created", "type", "created_at"),
        Index("idx_results_created_at", "created_at"),
    )
