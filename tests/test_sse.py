"""Tests for the server-sent event protocol."""

import json
from collections.abc import AsyncGenerator
from typing import cast

from langfuse import observe

from backend.cancellation import Cancellation
from backend.sse import HEADERS, MEDIA_TYPE, SSE, EventStreamResponse, ProgressFrame


class TestFrame:
    """Tests for the wire format one frame is written in."""

    def test_names_the_event_and_encodes_the_payload(self):
        """A frame is the event name, the JSON body, and a blank line."""
        assert SSE.frame("tick", {"n": 1}) == 'event: tick\ndata: {"n": 1}\n\n'

    def test_ends_with_a_blank_line(self):
        """Without the terminating blank line the client never dispatches."""
        assert SSE.frame("tick", {}).endswith("\n\n")

    def test_payload_is_json_not_repr(self):
        """A Python repr would decode as nothing on the other end."""
        body = SSE.frame("tick", {"ok": True}).split("data: ", 1)[1]

        assert json.loads(body) == {"ok": True}


class TestNamedFrames:
    """Tests for the three events the endpoints actually send."""

    def test_progress_carries_the_step_and_the_message(self):
        """The page shows both, so both have to survive the framing."""
        frame = SSE.progress("matching", "Matching selections...")

        assert frame.startswith("event: progress\n")
        assert json.loads(frame.split("data: ", 1)[1]) == {
            "step": "matching",
            "message": "Matching selections...",
        }

    def test_result_passes_the_payload_through(self):
        """The finished work is sent as-is, not wrapped."""
        frame = SSE.result({"tracks": []})

        assert frame.startswith("event: result\n")
        assert json.loads(frame.split("data: ", 1)[1]) == {"tracks": []}

    def test_error_wraps_the_message(self):
        """The page reads `message`, so a bare string would not show."""
        frame = SSE.error("boom")

        assert frame.startswith("event: error\n")
        assert json.loads(frame.split("data: ", 1)[1]) == {"message": "boom"}


class TestOf:
    """Tests for framing a model, so the wire matches the schema."""

    def test_a_model_is_framed_as_its_json_dump(self):
        frame = SSE.of("tick", ProgressFrame(step="matching", message="Matching..."))

        assert json.loads(frame.split("data: ", 1)[1]) == {
            "step": "matching",
            "message": "Matching...",
        }

    def test_json_mode_is_used_so_the_payload_survives_encoding(self):
        """`model_dump()` alone leaves datetimes and enums `json.dumps` refuses."""
        frame = SSE.of("tick", ProgressFrame(step="a", message="b"))

        assert json.loads(frame.split("data: ", 1)[1])


class TestServe:
    """Tests for serving a stream of frames."""

    def test_uses_the_event_stream_media_type(self):
        """A client only treats the body as events under this type."""
        response = SSE.serve(iter([]))

        assert response.media_type == MEDIA_TYPE

    def test_the_media_type_is_on_the_class_not_the_instance(self):
        """FastAPI reads it off `response_class` to document the route."""
        assert EventStreamResponse.media_type == MEDIA_TYPE

    def test_tells_proxies_not_to_buffer(self):
        """nginx otherwise holds every progress event until the stream ends."""
        response = SSE.serve(iter([]))

        assert response.headers["x-accel-buffering"] == HEADERS["X-Accel-Buffering"]
        assert response.headers["cache-control"] == "no-cache"


class TestWatching:
    """Tests for the run learning that its reader has gone."""

    def _steps(self, seen: list[bool]):
        """A pipeline that records whether anyone was reading at each step."""

        def frames():
            for step in range(3):
                seen.append(Cancellation.gone())
                yield f"event: tick\ndata: {step}\n\n"

        return frames()

    @staticmethod
    def _body(response: EventStreamResponse) -> AsyncGenerator[str]:
        """The response's stream, as the generator these tests close.

        Starlette types `body_iterator` as `AsyncIterable`, which promises
        neither `__anext__` nor `aclose`; what `SSE.serve` puts there is a
        generator, and closing one is what these tests are about.
        """
        return cast(AsyncGenerator[str], response.body_iterator)

    async def test_serves_every_frame_of_a_synchronous_stream(self):
        """Pumping the stream here must not change what reaches the client."""
        body = SSE.serve(self._steps([])).body_iterator

        assert [frame async for frame in body] == [
            f"event: tick\ndata: {step}\n\n" for step in range(3)
        ]

    async def test_a_closed_stream_tells_the_run_nobody_is_reading(self):
        """The step in flight finishes; the one after it must not start."""
        seen: list[bool] = []
        steps = self._steps(seen)

        body = self._body(SSE.serve(steps))
        assert await anext(body)
        await body.aclose()

        # The step the pipeline would run next, had it been resumed.
        next(steps, None)
        assert seen == [False, True]

    async def test_a_traced_stream_still_learns_its_reader_left(self):
        """The regression `watch_stream` exists for.

        `@observe` pins every step of a generator to the context it was built
        in. With the flag installed only by the pump, a traced pipeline read
        the context from before it existed and never saw the disconnect.
        """
        seen: list[bool] = []
        Cancellation.watch()
        steps = observe(name="traced")(self._steps)(seen)

        body = self._body(SSE.serve(steps))
        assert await anext(body)
        await body.aclose()

        next(steps, None)
        assert seen == [False, True]

    async def test_serves_an_asynchronous_stream_too(self):
        """The recommend round yields its own frames; only the pump differs."""

        async def frames():
            yield "event: tick\ndata: {}\n\n"

        body = SSE.serve(frames()).body_iterator

        assert [frame async for frame in body] == ["event: tick\ndata: {}\n\n"]
