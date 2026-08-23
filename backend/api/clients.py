"""The shared outbound clients the API holds open.

`SharedClients` builds each on first use rather than at startup: a deployment
with no recommendations never opens either, and building one costs a connection
pool. Entry point: the `shared` instance; `close()` runs on shutdown.
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING

import httpx

from backend.config.store import config_store

if TYPE_CHECKING:
    from backend.research import AlbumResearch


class SharedClients:
    """One research client and one art client, each opened on first use.

    Each is guarded by its own lock, taken only on the miss: two requests
    arriving together would otherwise each open a connection pool, and the one
    that lost would be dropped still open.
    """

    def __init__(self) -> None:
        self._research: AlbumResearch | None = None
        self._research_lock = threading.Lock()
        self._art: httpx.AsyncClient | None = None
        self._art_lock = asyncio.Lock()

    def research(self) -> AlbumResearch:
        """The album research client, built once.

        Imported lazily: it pulls in an HTML parser that a deployment without
        recommendations never needs.
        """
        if self._research is None:
            with self._research_lock:
                if self._research is None:
                    from backend.research import AlbumResearch

                    self._research = AlbumResearch.configured()
        return self._research

    async def art(self) -> httpx.AsyncClient:
        """The HTTP client both art proxies share.

        Rebuilt when closed: shutdown closes it, and a test may reuse the process.
        """
        if self._art is None or self._art.is_closed:
            async with self._art_lock:
                if self._art is None or self._art.is_closed:
                    self._art = httpx.AsyncClient(timeout=config_store.get().art.timeout)
        return self._art

    async def close(self) -> None:
        """Release both clients, on shutdown.

        Each is dropped after it closes, so a process that keeps running builds
        a fresh one rather than handing out a closed handle.
        """
        if self._research is not None:
            await self._research.close()
            self._research = None
        if self._art is not None:
            await self._art.aclose()
            self._art = None


# The single instance the API holds its outbound connections on.
shared = SharedClients()
