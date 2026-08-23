"""Critical reviews, read off whatever page MusicBrainz points at.

Every review is on a different publication's site, so the text is recovered
with readability rather than a per-site rule. What comes back is one article's
prose with the navigation, ads and related-links chrome removed.

The URLs are curated by MusicBrainz, not supplied by a user, but they still
point at third-party servers -- so every fetch goes through `SafeFetcher`.

Entry point: `Reviews`.
"""

import logging
import re
from typing import Final

import httpx
from readability import Document as ReadableDocument

from backend.config import ResearchConfig
from backend.research.http import SharedHttp
from backend.research.safety import SafeFetcher

logger = logging.getLogger(__name__)

TAGS: Final = re.compile(r"<[^>]+>")
WHITESPACE: Final = re.compile(r"\s+")


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
            fetcher = SafeFetcher(max_redirects=self.config.max_redirects)
            response = await fetcher.get(client, url)
            if response is None:
                return None
            response.raise_for_status()
            text = self.plain_text(response.text)
        except (httpx.HTTPError, ValueError) as err:
            logger.warning("Review fetch failed for %s: %s", url, err)
            return None

        if not text:
            return None
        return self.trimmed(text)

    @staticmethod
    def plain_text(html: str) -> str:
        """The readable article out of a page, as one run of prose."""
        readable = ReadableDocument(html).summary()
        return WHITESPACE.sub(" ", TAGS.sub(" ", readable)).strip()

    def trimmed(self, text: str) -> str:
        """Cut to the configured cap, on a sentence end when one is near it.

        A break below `review_min_chars` is ignored: cutting there throws away
        more than the tidy ending is worth.
        """
        cap = self.config.review_max_chars
        if len(text) <= cap:
            return text
        end = text.rfind(". ", self.config.review_min_chars, cap)
        return text[: (end + 1) if end != -1 else cap]
