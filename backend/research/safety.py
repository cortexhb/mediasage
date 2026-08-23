"""Whether a URL may be fetched, hop by hop.

Review links come from MusicBrainz and point at third-party servers, so a
fetch must not be allowed to reach the LAN. `SafeFetcher` checks the start and
every redirect target rather than trusting the first.

Subject to DNS rebinding: a name is resolved here and again by the fetch.
Accepted, because callers pass curated URLs and the alternative is pinning the
resolved address through httpx.
"""

import ipaddress
import logging
import socket

import httpx
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class SafeFetcher(BaseModel):
    """A fetch that refuses anything resolving inside the network."""

    model_config = ConfigDict(frozen=True)

    max_redirects: int

    @staticmethod
    def is_safe(url: str) -> bool:
        """Whether `url` is HTTP(S) and resolves only to public addresses."""
        try:
            parsed = httpx.URL(url)
        except httpx.InvalidURL, ValueError:
            return False

        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.host
        if not hostname:
            return False

        try:
            resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC)
        except socket.gaierror, UnicodeError, ValueError:
            return False

        for info in resolved:
            try:
                address = ipaddress.ip_address(info[4][0])
            except ValueError:
                return False
            if (
                address.is_private
                or address.is_loopback
                or address.is_link_local
                or address.is_reserved
            ):
                return False
        return True

    async def get(self, client: httpx.AsyncClient, url: str) -> httpx.Response | None:
        """Fetch `url`, re-checking every redirect target on the way.

        An open redirect on a public host would otherwise reach the LAN, so
        every hop is checked again rather than trusting the first.

        Args:
            client: The client to fetch through
            url: Where to start; checked before the first request

        Returns:
            The final response, or None when a hop was unsafe or there were
            too many
        """
        if not self.is_safe(url):
            logger.warning("Rejecting unsafe URL: %s", url)
            return None

        response = await client.get(url, follow_redirects=False)
        for _ in range(self.max_redirects):
            if not response.is_redirect:
                return response
            target = str(response.next_request.url) if response.next_request else ""
            if not target or not self.is_safe(target):
                logger.warning("Rejecting unsafe redirect: %s", target)
                return None
            response = await client.get(target, follow_redirects=False)

        logger.warning("Too many redirects from %s", url)
        return None
