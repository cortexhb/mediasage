"""Noticing that the client of a plain request has gone.

A streaming response learns this for free: Starlette listens for
`http.disconnect` and cancels the response. A plain one does not -- uvicorn
runs the handler to the end and drops the reply -- so an endpoint that spends
two LLM calls spends the second one for nobody. Polling `is_disconnected` is
the only signal available before the reply is written.

The flag it sets is `backend.cancellation`; what reads it is `LLMClient`.
"""

import asyncio
from collections.abc import AsyncGenerator

from fastapi import Request

from backend.api.background import background
from backend.cancellation import Cancellation

# `is_disconnected` is a receive-queue poll, so this is latency, not load.
POLL_SECONDS = 0.5


async def watch_client(request: Request) -> AsyncGenerator[None]:
    """Flag the run once its client disconnects.

    A module-level function because FastAPI demands the shape: it is a
    `Depends`, declared per route rather than taken as an argument, since no
    handler here uses the flag itself.
    """
    gone = Cancellation.watch()

    async def until_gone() -> None:
        while not await request.is_disconnected():
            await asyncio.sleep(POLL_SECONDS)
        gone.set()

    watcher = background.spawn(until_gone())
    try:
        yield
    finally:
        watcher.cancel()


async def watch_stream() -> None:
    """Install the client-gone flag before a streaming handler runs.

    A streaming route needs no poller -- Starlette cancels the pump on
    `http.disconnect` and `SSE` sets the flag from that. What it needs is the
    flag installed in the request's context rather than the pump's, because
    `@observe` pins a traced pipeline's steps to the context it was built in.

    Async, and a module-level function, because FastAPI demands both: a sync
    dependency runs in a threadpool, whose context the handler never sees.
    """
    Cancellation.watch()
