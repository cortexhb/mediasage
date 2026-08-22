"""Track filtering, as a model rather than a pair of parallel lists.

`TrackFilter` carries what the user asked for and knows how to express it as
SQLAlchemy predicates. Entry points: `TrackFilter.clauses` and
`TrackFilter.album_key_clause`.

The previous form returned `(list[str], list[Any])` and left every caller to
keep conditions and parameters aligned by hand. Building expressions instead
removes that obligation, and removes the string-built SQL with it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import ColumnElement, and_, exists, or_, select

from backend.library.constants import DECADE_SPAN
from backend.library.tables import Track, TrackGenre


class DecadeRange(BaseModel):
    """The inclusive year range one decade covers."""

    model_config = ConfigDict(frozen=True)

    start_year: int

    @property
    def end_year(self) -> int:
        return self.start_year + DECADE_SPAN

    @classmethod
    def parse(cls, label: str) -> DecadeRange | None:
        """Read a decade label like "1990s"; None when it is not one."""
        try:
            return cls(start_year=int(label.strip().rstrip("sS")))
        except (ValueError, TypeError):
            return None

    def clause(self) -> ColumnElement[bool]:
        return Track.year.between(self.start_year, self.end_year)


class TrackFilter(BaseModel):
    """What a caller wants kept, expressible as SQL."""

    model_config = ConfigDict(frozen=True)

    genres: list[str] = []
    decades: list[str] = []
    min_rating: int = 0
    exclude_live: bool = True

    @field_validator("genres", "decades")
    @classmethod
    def drop_blanks(cls, values: list[str]) -> list[str]:
        return [v.strip() for v in values if v and v.strip()]

    @property
    def genre_keys(self) -> list[str]:
        """The lowercased genre names `track_genres` is matched on."""
        return [genre.lower() for genre in self.genres]

    @property
    def decade_ranges(self) -> list[DecadeRange]:
        """The parseable decades; unrecognised labels are ignored, not fatal."""
        parsed = (DecadeRange.parse(label) for label in self.decades)
        return [decade for decade in parsed if decade is not None]

    def genre_clause(self) -> ColumnElement[bool]:
        """Match tracks carrying any of the requested genres."""
        return exists(
            select(TrackGenre.rating_key).where(
                TrackGenre.rating_key == Track.rating_key,
                TrackGenre.genre_lower.in_(self.genre_keys),
            )
        )

    def clauses(self, *, include_genres: bool = True) -> list[ColumnElement[bool]]:
        """Every predicate this filter implies.

        Args:
            include_genres: Whether to apply the genre predicate. Album queries
                select qualifying album keys separately, so they omit it here.

        Returns:
            Predicates to AND together; empty when nothing is filtered
        """
        clauses: list[ColumnElement[bool]] = []

        if self.exclude_live:
            clauses.append(Track.is_live.is_(False))

        if self.min_rating > 0:
            clauses.append(Track.user_rating >= self.min_rating)

        ranges = self.decade_ranges
        if ranges:
            clauses.append(or_(*[decade.clause() for decade in ranges]))

        if include_genres and self.genres:
            clauses.append(self.genre_clause())

        return clauses

    def album_key_clause(self) -> ColumnElement[bool] | None:
        """Restrict to albums where *some* surviving track carries a genre.

        An album qualifies on any of its tracks, so qualifying album keys are
        selected before aggregation rather than assembled albums being pruned
        after the fact.
        """
        if not self.genres:
            return None

        inner = select(Track.parent_rating_key).where(
            has_album_key(), *self.clauses(include_genres=True)
        )
        return Track.parent_rating_key.in_(inner)


def has_album_key() -> ColumnElement[bool]:
    """Tracks that belong to an identifiable album."""
    return and_(Track.parent_rating_key.is_not(None), Track.parent_rating_key != "")
