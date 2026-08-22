"""The HTTP client every lookup shares, and the rate limit one of them obeys.

Built on first use rather than at import: a deployment that never asks for a
recommendation never opens a connection pool.
"""

import asyncio
import time
from typing import Final

import httpx

# MusicBrainz requires a User-Agent that identifies the application and gives
# them somewhere to complain; a generic one is rate-limited harder or blocked.
USER_AGENT: Final = "MediaSage/1.0 (https://github.com/ecwilsonaz/mediasage)"


class Throttle:
    """One call per interval, across every caller that shares it.

    The lock is held across the sleep on purpose: releasing it early would let
    every waiter wake at once and burst straight through the limit.
    """

    def __init__(self, interval: float) -> None:
        self.interval = interval
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        """Block until the interval since the last call has passed."""
        async with self._lock:
            elapsed = time.monotonic() - self._last
            if elapsed < self.interval:
                await asyncio.sleep(self.interval - elapsed)
            self._last = time.monotonic()


class SharedHttp:
    """One httpx client, built on first use and reused until closed.

    Rebuilt when closed: shutdown closes it, and a test may reuse the process.
    """

    def __init__(self, timeout: float, user_agent: str = USER_AGENT) -> None:
        self.timeout = timeout
        self.user_agent = user_agent
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()

    async def client(self) -> httpx.AsyncClient:
        """The shared client, opening one if there is none."""
        if self._client is None or self._client.is_closed:
            async with self._lock:
                if self._client is None or self._client.is_closed:
                    self._client = httpx.AsyncClient(
                        timeout=self.timeout, headers={"User-Agent": self.user_agent}
                    )
        return self._client

    async def close(self) -> None:
        """Release the connection pool."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
