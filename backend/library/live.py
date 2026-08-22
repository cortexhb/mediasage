"""Deciding which tracks are live recordings rather than studio ones.

Plex does not mark live versions, so they are inferred from the title and album
text. What counts as live is the user's to configure; only the date format is
fixed. Entry point: `LiveVersionRule.of`.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, PrivateAttr

from backend.config import LibraryConfig
from backend.library.constants import DATE_PATTERN


class LiveVersionRule(BaseModel):
    """The configured test for a live recording.

    Built once per sync rather than per track: a large library runs this
    hundreds of thousands of times, so the patterns are compiled up front.
    """

    keywords: list[str] = []
    match_dated_titles: bool = True

    _keywords: re.Pattern[str] | None = PrivateAttr(default=None)
    _dates: re.Pattern[str] = PrivateAttr(default=re.compile(DATE_PATTERN))

    def model_post_init(self, context: object, /) -> None:
        """Compile the keyword alternation, if any keywords were configured."""
        words = "|".join(re.escape(word) for word in self.keywords if word.strip())
        if words:
            self._keywords = re.compile(rf"\b(?:{words})\b", re.IGNORECASE)

    @classmethod
    def of(cls, config: LibraryConfig) -> LiveVersionRule:
        """Build from the library configuration."""
        return cls(
            keywords=config.live_keywords,
            match_dated_titles=config.dated_titles_are_live,
        )

    def matches(self, title: str, album: str) -> bool:
        """Whether a track's title or album marks it as a live recording."""
        for text in (title, album):
            if self.match_dated_titles and self._dates.search(text):
                return True
            if self._keywords and self._keywords.search(text):
                return True
        return False
