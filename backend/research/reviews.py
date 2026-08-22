"""Critical reviews, read off whatever page MusicBrainz points at.

Every review is on a different publication's site, so the text is recovered
with readability rather than a per-site rule. What comes back is one article's
prose with the navigation, ads and related-links chrome removed.

The URLs are curated by MusicBrainz, not supplied by a user, but they still
point at third-party servers -- so every fetch goes through `safety`.

Entry point: `Reviews`.
"""

import logging
import re
from typing import Final

import httpx
from readability import Document as ReadableDocument

from backend.config import ResearchConfig
from backend.research.http import SharedHttp
from backend.research.safety import fetch_safely

logger = logging.getLogger(__name__)

TAGS: Final = re.compile(r"<[^>]+>")
WHITESPACE: Final = re.compile(r"\s+")


def plain_text(html: str) -> str:
    """The readable article out of a page, as one run of prose."""
    readable = ReadableDocument(html).summary()
    return WHITESPACE.sub(" ", TAGS.sub(" ", readable)).strip()


def trimmed(text: str, max_chars: int, min_chars: int) -> str:
    """Cut to `max_chars`, on a sentence end when there is one near it.

    Args:
        text: The article prose
        max_chars: Characters kept
        min_chars: Earliest character a sentence break is accepted at; below
            it the cut throws away more than the tidy ending is worth
    """
    if len(text) <= max_chars:
        return text
    end = text.rfind(". ", min_chars, max_chars)
    return text[: (end + 1) if end != -1 else max_chars]


class Reviews:
    """One review page, fetched and reduced to its article text."""

    def __init__(self, http: SharedHttp, config: ResearchConfig) -> None:
        self.http = http
        self.config = config

    async def text(self, url: str) -> str | None:
        """The article at `url`, or None when it cannot or must not be read."""
        # Blocked hosts are filtered when the relations are read, and again
        # here: a review URL can reach this from a saved session.
        if any(host in url for host in self.config.blocked_review_hosts):
            logger.info("Skipping %s: automated access is not permitted", url)
            return None

        client = await self.http.client()
        try:
            response = await fetch_safely(client, url, self.config.max_redirects)
            if response is None:
                return None
            response.raise_for_status()
            text = plain_text(response.text)
        except (httpx.HTTPError, ValueError) as err:
            logger.warning("Review fetch failed for %s: %s", url, err)
            return None

        if not text:
            return None
        return trimmed(text, self.config.review_max_chars, self.config.review_min_chars)
