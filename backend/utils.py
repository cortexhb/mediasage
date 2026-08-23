"""Comparing names two catalogues spelled differently.

`FuzzyMatcher` is the base every matcher inherits: the recommender's album
matcher and the generator's track matcher both compare a name a model wrote
against a name Plex filed, and both need the same folding before scoring.

Nothing here knows about Plex, a model, or the library.
"""

import re
from typing import Final

from pydantic import BaseModel, ConfigDict
from rapidfuzz import fuzz
from unidecode import unidecode

# Punctuation carries no matching signal and Plex is inconsistent about it.
_PUNCTUATION: Final = re.compile(r"[^\w\s]")


class FuzzyMatcher(BaseModel):
    """How close two names have to be before they count as the same thing.

    Subclasses carry the floors; the folding and the score are shared, because
    a matcher that folded differently would score differently.
    """

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def folded(text: str) -> str:
        """Lowercase, strip punctuation, and fold accents for comparison."""
        return unidecode(_PUNCTUATION.sub("", text.lower()))

    @classmethod
    def ratio(cls, left: str, right: str) -> float:
        """How alike two names are once folded, 0-100."""
        return fuzz.ratio(cls.folded(left), cls.folded(right))
