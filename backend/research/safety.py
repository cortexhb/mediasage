"""Whether a URL is safe to fetch, and following redirects while it stays so.

Review URLs come from MusicBrainz relations rather than from a user, but they
are still somebody else's data pointing at somebody else's server. Anything
resolving to a private address is refused, and every redirect hop is checked
again -- an open redirect on a public host would otherwise reach the LAN.

This is subject to DNS rebinding: the name is resolved here and again by the
fetch. Accepted, because the input is curated and the alternative is pinning
the resolved address through httpx.
"""

import ipaddress
import logging
import socket

import httpx

logger = logging.getLogger(__name__)


def is_safe(url: str) -> bool:
    """Whether `url` is HTTP(S) and resolves only to public addresses."""
    try:
        parsed = httpx.URL(url)
    except (httpx.InvalidURL, ValueError):
        return False

    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.host
    if not hostname:
        return False

    try:
        resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC)
    except (socket.gaierror, UnicodeError, ValueError):
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


async def fetch_safely(
    client: httpx.AsyncClient, url: str, max_redirects: int
) -> httpx.Response | None:
    """Fetch `url`, re-checking every redirect target on the way.

    Args:
        client: The shared research client
        url: Where to start; checked before the first request
        max_redirects: Hops followed before giving up

    Returns:
        The final response, or None when a hop was unsafe or there were too many
    """
    if not is_safe(url):
        logger.warning("Rejecting unsafe URL: %s", url)
        return None

    response = await client.get(url, follow_redirects=False)
    for _ in range(max_redirects):
        if not response.is_redirect:
            return response
        target = str(response.next_request.url) if response.next_request else ""
        if not target or not is_safe(target):
            logger.warning("Rejecting unsafe redirect: %s", target)
            return None
        response = await client.get(target, follow_redirects=False)

    logger.warning("Too many redirects from %s", url)
    return None
