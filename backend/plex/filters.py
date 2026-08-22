"""Turning a filter request into Plex search keyword arguments.

Plex filters on genre and decade server-side but has no notion of a live
version, so that half is applied after the rows come back. Entry point:
`PlexFilter`.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

# Plex names the field with the operator appended; `>>=` is "at least".
MIN_RATING_FIELD = "userRating>>="

# Fetched-to-requested ratio when live versions will be dropped afterwards,
# so a limited query still returns a full page after filtering.
LIVE_OVERFETCH = 1.3


class PlexFilter(BaseModel):
    """What to ask Plex for, and what to drop once it answers."""

    model_config = ConfigDict(frozen=True)

    genres: list[str] = []
    decades: list[str] = []
    min_rating: int = 0
    exclude_live: bool = True

    @field_validator("genres", "decades")
    @classmethod
    def drop_blanks(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value and value.strip()]

    @property
    def decade_values(self) -> list[str]:
        """Decades as Plex spells them: "1990s" is filed under "1990"."""
        return [decade.removesuffix("s").removesuffix("S") for decade in self.decades]

    def search_kwargs(self) -> dict[str, Any]:
        """Keyword arguments for a Plex search; empty when nothing is filtered."""
        kwargs: dict[str, Any] = {}
        if self.genres:
            kwargs["genre"] = self.genres
        if self.decades:
            kwargs["decade"] = self.decade_values
        if self.min_rating > 0:
            kwargs[MIN_RATING_FIELD] = self.min_rating
        return kwargs

    def fetch_count(self, limit: int) -> int:
        """How many rows to request so `limit` survive the live filter."""
        if limit <= 0:
            return 0
        return int(limit * LIVE_OVERFETCH) if self.exclude_live else limit
