"""The shared outbound clients the API holds open.

Both are built on first use rather than at startup: a deployment with no
recommendations never opens either, and building one costs a connection pool.
`close()` runs on shutdown.
"""

import asyncio
import threading

import httpx

from backend.config.store import config_store

_research: object | None = None
_research_lock = threading.Lock()

_art: httpx.AsyncClient | None = None
_art_lock = asyncio.Lock()


def research():
    """The album research client, built once.

    Imported lazily: it pulls in an HTML parser that a deployment without
    recommendations never needs.
    """
    global _research
    if _research is None:
        with _research_lock:
            if _research is None:
                from backend.research import AlbumResearch

                _research = AlbumResearch()
    return _research


async def art() -> httpx.AsyncClient:
    """The HTTP client both art proxies share.

    Rebuilt when closed: shutdown closes it, and a test may reuse the process.
    """
    global _art
    if _art is None or _art.is_closed:
        async with _art_lock:
            if _art is None or _art.is_closed:
                _art = httpx.AsyncClient(timeout=config_store.get().art.timeout)
    return _art


async def close() -> None:
    """Release both clients, on shutdown."""
    if _research is not None:
        await _research.close()
    if _art is not None:
        await _art.aclose()
