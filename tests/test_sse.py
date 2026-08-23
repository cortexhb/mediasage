"""Tests for the server-sent event protocol."""

import json

from backend.sse import HEADERS, MEDIA_TYPE, SSE


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


class TestServe:
    """Tests for serving a stream of frames."""

    def test_uses_the_event_stream_media_type(self):
        """A client only treats the body as events under this type."""
        response = SSE.serve(iter([]))

        assert response.media_type == MEDIA_TYPE

    def test_tells_proxies_not_to_buffer(self):
        """nginx otherwise holds every progress event until the stream ends."""
        response = SSE.serve(iter([]))

        assert response.headers["x-accel-buffering"] == HEADERS["X-Accel-Buffering"]
        assert response.headers["cache-control"] == "no-cache"
