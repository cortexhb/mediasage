"""``/api/library/search`` -- tracks matching a query, read from Plex."""

import asyncio
from typing import Annotated, Final

from fastapi import Depends, FastAPI, Query

from backend.models import Track
from backend.plex import PlexClient, plex_store

# iOS auto-correction turns a typed quote into a curly one, which matches
# nothing in the library.
SMART_QUOTES: Final = str.maketrans(
    {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'}
)


async def _search(
    plex: Annotated[PlexClient, Depends(plex_store.require)],
    q: str = Query(..., description="Search query"),
) -> list[Track]:
    """``GET /api/library/search`` -- tracks matching a query, from Plex."""
    return await asyncio.to_thread(plex.library.search, q.translate(SMART_QUOTES))


def register_search_routes(app: FastAPI) -> None:
    app.add_api_route(
        "/api/library/search", _search, methods=["GET"], response_model=list[Track]
    )
