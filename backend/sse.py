"""Server-sent events, framed in one place.

Two endpoints stream progress while they work, and the packages behind them
yield the frames. Both halves used to build the wire format by hand, so a
missing newline was a silently broken stream.

Top-level rather than under `api/`: `backend.generator` yields frames too, and
importing the HTTP layer from a domain package would be a cycle.

`SSE` is the protocol rather than one message: a frame is a string on the wire
by the time anything holds it, so what is worth owning is how one is written
and how a stream of them is served.
"""

import json
from collections.abc import AsyncIterator, Iterator
from functools import partial
from typing import Any, Final

import anyio.to_thread
from pydantic import BaseModel, ConfigDict
from starlette.responses import StreamingResponse

from backend.cancellation import Cancellation

MEDIA_TYPE: Final = "text/event-stream"

# `X-Accel-Buffering: no` stops nginx and other reverse proxies from buffering
# the body, which otherwise holds every progress event until the stream ends.
HEADERS: Final = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class EventStreamResponse(StreamingResponse):
    """A stream that names its media type as a class attribute.

    FastAPI reads `media_type` off the response class when it builds the
    schema; without it a streaming route is documented as `application/json`.
    """

    media_type = MEDIA_TYPE


class ProgressFrame(BaseModel):
    """A step the user is shown while they wait."""

    step: str
    message: str


class ErrorFrame(BaseModel):
    """A failure the user is shown instead of a result."""

    message: str


class SSE(BaseModel):
    """The event-stream protocol: how one frame is written, and how many are served."""

    model_config = ConfigDict(frozen=True)

    @staticmethod
    def frame(event: str, data: dict[str, Any]) -> str:
        """One SSE frame: a named event and its JSON payload."""
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    @classmethod
    def of(cls, event: str, payload: BaseModel) -> str:
        """One frame carrying a model, so the wire cannot drift from the schema."""
        return cls.frame(event, payload.model_dump(mode="json"))

    @classmethod
    def progress(cls, step: str, message: str) -> str:
        """A step the user is shown while they wait."""
        return cls.of("progress", ProgressFrame(step=step, message=message))

    @classmethod
    def result(cls, payload: dict[str, Any]) -> str:
        """The finished work; the last frame of a successful stream."""
        return cls.frame("result", payload)

    @classmethod
    def error(cls, message: str) -> str:
        """A failure the user is shown instead of a result."""
        return cls.of("error", ErrorFrame(message=message))

    @staticmethod
    def serve(events: Iterator[str] | AsyncIterator[str]) -> EventStreamResponse:
        """Serve an iterator of frames as an event stream.

        Every stream is pumped here rather than by Starlette, so the run learns
        that its reader has gone: `StreamingResponse` cancels this pump on
        `http.disconnect`, and `Cancellation` carries that into the worker
        threads the pipelines run in.
        """
        return EventStreamResponse(SSE._watched(events), headers=HEADERS)

    @staticmethod
    async def _watched(events: Iterator[str] | AsyncIterator[str]) -> AsyncIterator[str]:
        """Serve a stream under a flag that says whether anyone is reading.

        A worker thread cannot be interrupted, so the step in flight finishes
        and the pipeline suspends at its next `yield`. The flag is what stops
        the step after that from spending a call nobody will read.

        Reused rather than installed: `watch_stream` puts it in the request's
        context, which is the one a traced pipeline's steps run in.
        """
        gone = Cancellation.flag()
        try:
            if isinstance(events, AsyncIterator):
                async for frame in events:
                    yield frame
                return
            # One frame per thread hop, as `iterate_in_threadpool` does it.
            while True:
                frame = await anyio.to_thread.run_sync(partial(next, events, None))
                if frame is None:
                    return
                yield frame
        finally:
            gone.set()
