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
        """The cover art URL for an album, or None when neither endpoint has one.

        Each endpoint is followed to the image it redirects to. An mbid we do
        not have is skipped rather than requested.
        """
        endpoints = (("release", release_mbid), ("release-group", release_group_mbid))
        for kind, mbid in endpoints:
            if not mbid:
                continue

            client = await self.http.client()
            try:
                response = await client.get(
                    f"{self.config.cover_art_url}/{kind}/{mbid}/front", follow_redirects=True
                )
            except httpx.HTTPError as err:
                logger.warning("Cover Art Archive %s %s failed: %s", kind, mbid, err)
                continue

            # 404 is the ordinary answer for an album nobody uploaded art for.
            if response.status_code == 200:
                return str(response.url)

        return None
