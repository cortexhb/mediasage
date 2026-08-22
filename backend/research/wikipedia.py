"""Wikipedia: the article text a pitch is grounded in.

The MediaWiki extracts API returns the whole article as plain text. Most of it
is tables rendered as prose -- charts, certifications, personnel lists -- which
is tokens spent on nothing a pitch can use, so those sections are dropped
before the text goes near a prompt.

A release group sometimes carries only a Wikidata relation, which is resolved
to the English article here.

Entry point: `Wikipedia`.
"""

import logging
import re
from typing import Final
from urllib.parse import unquote

import httpx

from backend.config import ResearchConfig
from backend.research.http import SharedHttp

logger = logging.getLogger(__name__)

WIKIDATA_SITELINK: Final = (
    "https://www.wikidata.org/w/rest.php/wikibase/v1/entities/items/{qid}/sitelinks/enwiki"
)

# MediaWiki section headers, kept by the split so each can be judged.
HEADER: Final = re.compile(r"(^={2,}\s*.+?\s*={2,}\s*$)", re.MULTILINE)
HEADER_TITLE: Final = re.compile(r"^={2,}\s*(.+?)\s*={2,}\s*$")


def useful_sections(text: str, max_chars: int, drop_sections: list[str]) -> str:
    """The article with its table-like sections removed and a cap applied.

    Args:
        text: The plain-text extract, section headers included
        max_chars: Characters kept after filtering
        drop_sections: A section whose title contains one of these is dropped;
            the lead section has no title and is always kept
    """
    kept: list[str] = []
    dropping = False

    for part in HEADER.split(text):
        title = HEADER_TITLE.match(part.strip())
        if title:
            dropping = any(word in title.group(1).lower() for word in drop_sections)
        if not dropping:
            kept.append(part)

    return _capped("".join(kept).strip(), max_chars)


def _capped(text: str, max_chars: int) -> str:
    """Cut to `max_chars`, on a paragraph break when one is near enough.

    Falling back to a hard cut past the halfway mark: an article whose first
    paragraph is longer than the cap has no break to use.
    """
    if len(text) <= max_chars:
        return text
    break_at = text[:max_chars].rfind("\n\n")
    return text[: break_at if break_at > max_chars // 2 else max_chars].strip()


class Wikipedia:
    """Article text, and the Wikidata hop that sometimes precedes it."""

    def __init__(self, http: SharedHttp, config: ResearchConfig) -> None:
        self.http = http
        self.config = config

    async def summary(self, article_url: str) -> str | None:
        """The useful part of one article, or None when it cannot be read."""
        title = _title_of(article_url)
        if not title:
            return None

        client = await self.http.client()
        try:
            response = await client.get(self.config.wikipedia_api_url, params={
                "action": "query",
                "titles": title,
                "prop": "extracts",
                "explaintext": "true",
                "format": "json",
            })
            response.raise_for_status()
            pages = response.json().get("query", {}).get("pages", {})
        except (httpx.HTTPError, ValueError) as err:
            logger.warning("Wikipedia fetch failed for %s: %s", article_url, err)
            return None

        if not pages:
            return None
        # One title was asked for, so there is one page; a miss is page "-1"
        # with no extract, which falls out as None below.
        extract = next(iter(pages.values())).get("extract", "")
        if not extract:
            return None
        return useful_sections(
            extract, self.config.wikipedia_max_chars, self.config.wikipedia_drop_sections
        )

    async def article_for(self, wikidata_url: str) -> str | None:
        """The English article a Wikidata item links to, if it has one."""
        qid = wikidata_url.rstrip("/").rpartition("/")[2]
        if not qid.startswith("Q"):
            return None

        client = await self.http.client()
        try:
            response = await client.get(WIKIDATA_SITELINK.format(qid=qid))
            if response.status_code != 200:
                return None
            return response.json().get("url")
        except (httpx.HTTPError, ValueError) as err:
            logger.warning("Wikidata resolution failed for %s: %s", wikidata_url, err)
            return None


def _title_of(article_url: str) -> str | None:
    """The article title out of its URL, percent-decoded."""
    _, marker, title = article_url.rstrip("/").partition("/wiki/")
    return unquote(title) if marker and title else None
