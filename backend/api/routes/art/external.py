"""``/api/external-art`` -- one cover from the Cover Art Archive.

Proxied so the page does not hotlink a third-party CDN, and because the
browser cannot follow the archive's redirect chain for us. `ExternalArt` owns
the CDN allowlist and the redirect walk that re-checks it on every hop.
"""

import logging
from typing import Final, Self
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict

from backend.api.clients import shared
from backend.api.routes.art.caching import CachePolicy
from backend.config import ArtConfig, config_store

logger = logging.getLogger(__name__)

# Redirect statuses followed by hand; every target is checked again.
REDIRECT_STATUSES: Final[frozenset[int]] = frozenset({301, 302, 303, 307, 308})


class ExternalArt(BaseModel):
    """The art CDN allowlist, and a fetch that honours it on every hop.

    Deliberately not `research.SafeFetcher`: that one asks whether a URL
    resolves outside the LAN, which a deployment mirroring cover art onto its
    own network needs to be allowed to do. Here the operator's allowlist is
    the containment, and it is stricter -- an address off it is refused
    whether it is public or not.
    """

    model_config = ConfigDict(frozen=True)

    domains: list[str]
    max_redirects: int

    @classmethod
    def of(cls, art: ArtConfig) -> Self:
        """The allowlist and hop budget a deployment configured."""
        return cls(domains=art.external_domains, max_redirects=art.max_redirects)

    def allows(self, url: str) -> bool:
        """Whether `url` is HTTPS and on the art CDN allowlist.

        Subdomains count: the Cover Art Archive redirects through archive.org
        to CDN hosts named dn710808.ca.archive.org or ia800123.us.archive.org.
        """
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        host = parsed.hostname or ""
        return any(host == domain or host.endswith(f".{domain}") for domain in self.domains)

    async def get(self, client: httpx.AsyncClient, url: str) -> httpx.Response | None:
        """Fetch `url`, re-checking the allowlist on every redirect target.

        Redirects are followed by hand because httpx would follow them
        anywhere: an open redirect on an allowed host would otherwise turn
        this endpoint into a proxy for anything.

        Args:
            client: The client to fetch through
            url: Where to start; the caller checks it before calling

        Returns:
            The image response, or None when a hop was refused, the upstream
            answered something else, or there were too many hops
        """
        current = url
        for _ in range(self.max_redirects):
            response = await client.get(current, follow_redirects=False)
            if response.status_code == 200:
                return response
            if response.status_code not in REDIRECT_STATUSES:
                return None
            redirect = response.headers.get("location", "")
            if not redirect or not self.allows(redirect):
                return None
            current = redirect
        return None


async def _external_art(url: str = Query(...)) -> Response:
    """``GET /api/external-art`` -- one cover from the Cover Art Archive."""
    art = config_store.get().art
    if urlparse(url).scheme != "https":
        raise HTTPException(status_code=400, detail="Only HTTPS URLs allowed")
    source = ExternalArt.of(art)
    if not source.allows(url):
        raise HTTPException(status_code=400, detail="Domain not allowed")

    try:
        client = await shared.art()
        response = await source.get(client, url)
        if response is not None:
            policy = CachePolicy(max_age=art.external_cache_max_age)
            return Response(
                content=response.content,
                media_type=response.headers.get("content-type", "image/jpeg"),
                headers={"Cache-Control": policy.header},
            )
    except Exception:
        logger.debug("External art proxy failed for url=%s", url, exc_info=True)

    raise HTTPException(status_code=404, detail="Art not available")


def register_external_art_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/external-art",
        _external_art,
        methods=["GET"],
        response_model=None,
        operation_id="getExternalArt",
    )
