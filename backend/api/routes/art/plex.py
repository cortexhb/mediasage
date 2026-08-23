"""``/api/art`` -- one track's cover, proxied from Plex.

Proxied so the Plex token never reaches the browser. The `ETag` is derived
from the thumb path, which Plex remints per artwork, so the cache entry is
immutable and a repeat view costs a 304.
"""

import asyncio
import hashlib
import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response

from backend.api.clients import shared
from backend.api.routes.art.caching import CachePolicy
from backend.config import config_store
from backend.plex import PlexClient, plex_store

logger = logging.getLogger(__name__)


async def _album_art(
    rating_key: str,
    request: Request,
    plex: Annotated[PlexClient, Depends(plex_store.require)],
) -> Response:
    """``GET /api/art/{rating_key}`` -- one track's cover, from Plex."""
    if not rating_key.isdigit():
        raise HTTPException(status_code=400, detail="Invalid rating key format")

    # Plex mints a new thumb path per artwork, so never stale.
    policy = CachePolicy(max_age=config_store.get().art.cache_max_age, immutable=True)

    thumb_path = await asyncio.to_thread(plex.library.thumb_path, rating_key)
    if thumb_path:
        etag = f'"{hashlib.md5(thumb_path.encode()).hexdigest()}"'
        if request.headers.get("if-none-match") == etag:
            return Response(
                status_code=304, headers={"Cache-Control": policy.header, "ETag": etag}
            )

        config = config_store.get()
        try:
            client = await shared.art()
            response = await client.get(
                f"{config.plex.url}{thumb_path}",
                headers={"X-Plex-Token": config.plex.token.get_secret_value()},
            )
            if response.status_code == 200:
                return Response(
                    content=response.content,
                    media_type=response.headers.get("content-type", "image/jpeg"),
                    headers={"Cache-Control": policy.header, "ETag": etag},
                )
        except Exception:
            logger.debug("Plex art proxy failed for rating_key=%s", rating_key, exc_info=True)

    raise HTTPException(status_code=404, detail="Art not available")


def register_plex_art_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/art/{rating_key}", _album_art, methods=["GET"], response_model=None
    )
