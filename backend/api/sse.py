"""Server-sent events, framed in one place.

Two endpoints stream progress while they work. Both used to build the wire
format by hand, so a missing newline was a silently broken stream.
"""

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any

from starlette.responses import StreamingResponse

MEDIA_TYPE = "text/event-stream"

# `X-Accel-Buffering: no` stops nginx and other reverse proxies from buffering
# the body, which otherwise holds every progress event until the stream ends.
HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def frame(event: str, data: dict[str, Any]) -> str:
    """One SSE frame: a named event and its JSON payload."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def progress(step: str, message: str) -> str:
    """A step the user is shown while they wait."""
    return frame("progress", {"step": step, "message": message})


def result(payload: dict[str, Any]) -> str:
    """The finished work; the last frame of a successful stream."""
    return frame("result", payload)


def error(message: str) -> str:
    """A failure the user is shown instead of a result."""
    return frame("error", {"message": message})


def stream(events: Iterator[str] | AsyncIterator[str]) -> StreamingResponse:
    """Serve an iterator of frames as an event stream."""
    return StreamingResponse(events, media_type=MEDIA_TYPE, headers=HEADERS)
