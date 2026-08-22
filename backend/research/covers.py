"""Cover Art Archive: front cover art for an album we have none for.

Two endpoints, because a specific release often has no art of its own while
the group it belongs to does -- the archive aggregates every edition's art
under the release group.

Both redirect to a CDN host; the final URL is what is returned, and the page
reaches it through the art proxy rather than fetching it directly.

Entry point: `CoverArt`.
"""

import logging

import httpx

from backend.config import ResearchConfig
from backend.research.http import SharedHttp

logger = logging.getLogger(__name__)


class CoverArt:
    """Front cover lookup, release first and release group second."""

    def __init__(self, http: SharedHttp, config: ResearchConfig) -> None:
        self.http = http
        self.config = config

    async def front(self, release_mbid: str, release_group_mbid: str = "") -> str | None:
        """The cover art URL for an album, or None when there is none."""
        found = await self._front_of("release", release_mbid)
        if found:
            return found
        return await self._front_of("release-group", release_group_mbid)

    async def _front_of(self, kind: str, mbid: str) -> str | None:
        """One archive endpoint, followed to the image it redirects to."""
        if not mbid:
            return None

        client = await self.http.client()
        try:
            response = await client.get(
                f"{self.config.cover_art_url}/{kind}/{mbid}/front", follow_redirects=True
            )
        except httpx.HTTPError as err:
            logger.warning("Cover Art Archive %s %s failed: %s", kind, mbid, err)
            return None

        # 404 is the ordinary answer for an album nobody has uploaded art for.
        return str(response.url) if response.status_code == 200 else None
