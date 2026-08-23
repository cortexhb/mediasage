"""What every request did, and how long it took to answer.

Entry point: `RequestLog`, wrapped around the app in `create_app`.

Two lines per request, not one. A single line written on completion says
nothing at all while a request is hanging, which is exactly when the log is
being read -- so arrival is logged before the app is called.

Pure ASGI rather than `BaseHTTPMiddleware`: that one consumes the response
body to re-emit it, which stalls the SSE routes until they finish. This one
only watches the frames go past.

The answer is timed to the response headers, not the body, so a stream
reports how long it took to open rather than how long it ran.
"""

import logging
import time
from typing import Final

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Logged at DEBUG: one page load makes dozens of these.
QUIET: Final = ("/static", "/assets", "/api/art")

# Above this a request is worth noticing even when it succeeded.
SLOW_MS: Final = 1000.0


class RequestLog:
    """ASGI middleware logging method, path, status and duration."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        target = self.target(scope)
        method = scope.get("method", "?")
        quiet = logging.DEBUG if scope.get("path", "").startswith(QUIET) else logging.INFO

        logger.log(quiet, "%s %s started", method, target)
        started = time.perf_counter()

        async def watched(message: Message) -> None:
            if message["type"] == "http.response.start":
                elapsed_ms = (time.perf_counter() - started) * 1000
                logger.log(
                    self.severity(quiet, message["status"], elapsed_ms),
                    "%s %s %d in %.0fms",
                    method,
                    target,
                    message["status"],
                    elapsed_ms,
                )
            await send(message)

        await self.app(scope, receive, watched)

    @staticmethod
    def target(scope: Scope) -> str:
        """The path, with the query string when there is one."""
        path = scope.get("path", "")
        query = scope.get("query_string", b"").decode("latin-1")
        return f"{path}?{query}" if query else path

    @staticmethod
    def severity(quiet: int, status: int, elapsed_ms: float) -> int:
        """How loudly to report an outcome, never below its arrival line."""
        if status >= 500:
            return logging.ERROR
        if status >= 400 or elapsed_ms >= SLOW_MS:
            return logging.WARNING
        return quiet
