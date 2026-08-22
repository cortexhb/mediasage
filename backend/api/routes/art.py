"""``/api/art`` and ``/api/external-art`` -- album art, proxied.

Plex art is proxied so the Plex token never reaches the browser. External art
is proxied so the page does not hotlink a third-party CDN, and because the
browser cannot follow the Cover Art Archive's redirect chain for us.
"""

import asyncio
import hashlib
import logging
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query, Request, Response

from backend.api import clients, guards
from backend.config import ArtConfig
from backend.config.store import config_store

logger = logging.getLogger(__name__)


def settings() -> ArtConfig:
    """The configured allowlist and cache lifetimes, read at call time."""
    return config_store.get().art


def cache_control(max_age: int, immutable: bool = False) -> str:
    """A `Cache-Control` header for art a browser may keep for `max_age`."""
    return f"public, max-age={max_age}" + (", immutable" if immutable else "")


def _is_allowed(url: str, domains: list[str]) -> bool:
    """Whether a URL is HTTPS and on the art CDN allowlist.

    Subdomains count: the Cover Art Archive redirects through archive.org to
    CDN hosts named dn710808.ca.archive.org or ia800123.us.archive.org.

    Re-checked on every redirect hop: an open redirect on an allowed host would
    otherwise turn this endpoint into a proxy for anything.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    host = parsed.hostname or ""
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


async def _album_art(rating_key: str, request: Request, plex: guards.Plex) -> Response:
    """``GET /api/art/{rating_key}`` -- one track's cover, from Plex."""
    if not rating_key.isdigit():
        raise HTTPException(status_code=400, detail="Invalid rating key format")

    # Plex mints a new thumb path when artwork changes, so a cached image
    # is never stale for the path it was fetched under.
    cacheable = cache_control(settings().cache_max_age, immutable=True)

    thumb_path = await asyncio.to_thread(plex.thumb_path, rating_key)
    if thumb_path:
        etag = f'"{hashlib.md5(thumb_path.encode()).hexdigest()}"'
        if request.headers.get("if-none-match") == etag:
            return Response(
                status_code=304, headers={"Cache-Control": cacheable, "ETag": etag}
            )

        config = guards.config()
        try:
            client = await clients.art()
            response = await client.get(
                f"{config.plex.url}{thumb_path}",
                headers={"X-Plex-Token": config.plex.token},
            )
            if response.status_code == 200:
                return Response(
                    content=response.content,
                    media_type=response.headers.get("content-type", "image/jpeg"),
                    headers={"Cache-Control": cacheable, "ETag": etag},
                )
        except Exception:
            logger.debug("Plex art proxy failed for rating_key=%s", rating_key, exc_info=True)

    raise HTTPException(status_code=404, detail="Art not available")


async def _external_art(url: str = Query(...)) -> Response:
    """``GET /api/external-art`` -- one cover from the Cover Art Archive."""
    art = settings()
    if urlparse(url).scheme != "https":
        raise HTTPException(status_code=400, detail="Only HTTPS URLs allowed")
    if not _is_allowed(url, art.external_domains):
        raise HTTPException(status_code=400, detail="Domain not allowed")

    try:
        client = await clients.art()
        # Redirects are followed by hand so each hop is checked against the
        # allowlist; httpx would follow them anywhere.
        current = url
        for _ in range(art.max_redirects):
            response = await client.get(current, follow_redirects=False)
            if response.status_code == 200:
                return Response(
                    content=response.content,
                    media_type=response.headers.get("content-type", "image/jpeg"),
                    headers={"Cache-Control": cache_control(art.external_cache_max_age)},
                )
            if response.status_code not in (301, 302, 303, 307, 308):
                break
            redirect = response.headers.get("location", "")
            if not redirect or not _is_allowed(redirect, art.external_domains):
                break
            current = redirect
    except Exception:
        logger.debug("External art proxy failed for url=%s", url, exc_info=True)

    raise HTTPException(status_code=404, detail="Art not available")


def register_art_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/art/{rating_key}", _album_art, methods=["GET"], response_model=None
    )
    app.add_api_route("/api/external-art", _external_art, methods=["GET"], response_model=None)
