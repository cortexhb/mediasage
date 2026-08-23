"""Models for saved generation results.

The shapes the store reads and writes. `ResultListItem` deliberately omits the
snapshot: a history page would otherwise carry every track of every result.

`SavedResult` carries the snapshot as the JSON column holds it. The API narrows
that to a discriminated union in `backend.models`, which cannot be done here --
the snapshot's two shapes live in packages that import this one.
"""

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel

from backend.results.tables import Result

# What produced a result, deciding how the UI renders it.
ResultType = Literal["prompt_playlist", "seed_playlist", "album_recommendation"]


class ResultFields(BaseModel):
    """Every column of a saved result except the two that vary by shape.

    `type` is declared by each subclass rather than here: the API narrows it to
    one literal per snapshot shape, and narrowing an inherited mutable field is
    an unsound override.
    """

    id: str
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


class ResultListItem(ResultFields):
    """A saved result as it appears in the history feed."""

    type: ResultType


class ResultListResponse(BaseModel):
    """One page of history, with the total behind it."""

    results: list[ResultListItem] = []
    total: int = 0


class SavedResult(ResultFields):
    """A saved result including the snapshot needed to render it.

    `snapshot` is untyped here on purpose: it is whatever the JSON column
    holds, and narrowing it is the API layer's job.
    """

    type: ResultType
    snapshot: dict[str, Any] = {}
