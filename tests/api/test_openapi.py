"""Tests for the schema the TypeScript client is generated from.

Every claim here is one the SPA's generated types depend on. A route that
drifts from them still works over HTTP and still produces a client that cannot
express what it returns, which is why they are asserted rather than assumed.
"""

import pytest

from backend.main import app

SCHEMA = app.openapi()

STREAMS = ("/api/generate/stream", "/api/recommend/generate")


def operations() -> list[tuple[str, str, dict]]:
    """Every path, method and operation the schema declares."""
    return [
        (path, method, operation)
        for path, methods in SCHEMA["paths"].items()
        for method, operation in methods.items()
    ]


class TestOperationIds:
    """Codegen names its functions after these."""

    @pytest.mark.parametrize(("path", "method", "operation"), operations())
    def test_every_route_names_itself(self, path, method, operation):
        """Unset, FastAPI derives `_get_config_api_config_get` from the handler."""
        assert "operation_id" not in operation
        assert f"{method}_" not in operation["operationId"]

    def test_no_two_routes_share_a_name(self):
        """A duplicate silently overwrites the other in the generated client."""
        ids = [operation["operationId"] for _, _, operation in operations()]

        assert len(ids) == len(set(ids))


class TestResultDetail:
    """The saved snapshot is a discriminated union, not an opaque object."""

    def schema_of(self) -> dict:
        return SCHEMA["paths"]["/api/results/{result_id}"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]

    def test_the_two_shapes_are_both_offered(self):
        refs = {member["$ref"].rsplit("/", 1)[-1] for member in self.schema_of()["oneOf"]}

        assert refs == {"PlaylistResultDetail", "AlbumResultDetail"}

    def test_type_discriminates_between_them(self):
        """Without this the generated union cannot be narrowed by a `switch`."""
        discriminator = self.schema_of()["discriminator"]

        assert discriminator["propertyName"] == "type"
        assert set(discriminator["mapping"]) == {
            "prompt_playlist",
            "seed_playlist",
            "album_recommendation",
        }

    def test_the_history_feed_types_are_an_enum_not_a_string(self):
        listed = SCHEMA["components"]["schemas"]["ResultListItem"]["properties"]["type"]

        assert listed["enum"] == ["prompt_playlist", "seed_playlist", "album_recommendation"]


class TestStreams:
    """Both streaming routes describe the frames they put on the wire."""

    @pytest.mark.parametrize("path", STREAMS)
    def test_the_body_is_declared_as_an_event_stream(self, path):
        """Documented as JSON, a generated client would try to parse it as one."""
        content = SCHEMA["paths"][path]["post"]["responses"]["200"]["content"]

        assert list(content) == ["text/event-stream"]

    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            (
                "/api/generate/stream",
                {
                    "ProgressFrame",
                    "NarrativeFrame",
                    "TracksFrame",
                    "PlaylistCompleteFrame",
                    "ErrorFrame",
                },
            ),
            (
                "/api/recommend/generate",
                {"ProgressFrame", "RecommendResultFrame", "ErrorFrame"},
            ),
        ],
    )
    def test_every_frame_it_can_send_is_named(self, path, expected):
        members = SCHEMA["paths"][path]["post"]["responses"]["200"]["content"]["text/event-stream"][
            "schema"
        ]["anyOf"]

        assert {member["$ref"].rsplit("/", 1)[-1] for member in members} == expected
