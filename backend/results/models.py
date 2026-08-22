"""Models for saved generation results.

The shapes the results API returns. `ResultListItem` deliberately omits the
snapshot: a history page would otherwise carry every track of every result.
"""

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel

from backend.results.tables import Result

# What produced a result, deciding how the UI renders it.
ResultType = Literal["prompt_playlist", "seed_playlist", "album_recommendation"]


class ResultListItem(BaseModel):
    """A saved result as it appears in the history feed."""

    id: str
    type: str
    title: str
    prompt: str
    track_count: int
    artist: str | None = None
    art_rating_key: str | None = None
    subtitle: str | None = None
    created_at: datetime

    @classmethod
    def of(cls, result: Result) -> Self:
        """Build from a `results` row; subclasses get their own type back."""
        return cls.model_validate(result, from_attributes=True)


class ResultListResponse(BaseModel):
    """One page of history, with the total behind it."""

    results: list[ResultListItem] = []
    total: int = 0


class ResultDetail(ResultListItem):
    """A saved result including the snapshot needed to render it."""

    snapshot: dict[str, Any] = {}
