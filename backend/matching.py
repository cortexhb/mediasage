"""Text normalization for matching model output against library entries.

The LLM answers with titles and artists as it remembers them; the library
spells them its own way. These helpers strip the differences that do not carry
meaning before a fuzzy comparison. Entry points: `simplify`, `artist_variants`,
`threshold`.
"""

import re
from typing import Final

from unidecode import unidecode

from backend.config.store import config_store


def threshold() -> int:
    """The configured rapidfuzz floor below which a track is not the same one."""
    return config_store.get().matching.track_threshold


# Punctuation carries no matching signal and Plex is inconsistent about it.
_PUNCTUATION: Final = re.compile(r"[^\w\s]")


def simplify(text: str) -> str:
    """Lowercase, strip punctuation, and fold accents for comparison."""
    return unidecode(_PUNCTUATION.sub("", text.lower()))


def artist_variants(name: str) -> list[str]:
    """Spellings of one artist name that libraries use interchangeably.

    Only the ampersand split matters in practice: "Hall and Oates" and
    "Hall & Oates" are the same act filed two ways.
    """
    variants = [name]
    if " and " in name.lower():
        variants.append(name.replace(" and ", " & ").replace(" And ", " & "))
    elif " & " in name:
        variants.append(name.replace(" & ", " and "))
    return variants
