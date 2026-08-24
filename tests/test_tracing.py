"""What `Tracing` sends, and what it refuses to send.

The point of these is the off state: an unconfigured deployment, and the test
suite itself, must attach no handler and export nothing.
"""

import pytest
from pydantic import SecretStr

from backend.config import LangfuseConfig
from backend.tracing import SESSION_KEY, Tracing


@pytest.fixture
def unconfigured():
    """A section with nothing set, as a deployment that wants no tracing."""
    return LangfuseConfig()


@pytest.fixture
def configured():
    """A section with all three values, as a deployment that wants tracing."""
    return LangfuseConfig(
        base_url="https://langfuse.example",
        public_key="pk-lf-test",
        secret_key="sk-lf-test",
    )


class TestIsConfigured:
    def test_nothing_set_is_off(self, unconfigured):
        assert unconfigured.is_configured is False

    @pytest.mark.parametrize(
        "missing", [{"base_url": ""}, {"public_key": ""}, {"secret_key": SecretStr("")}]
    )
    def test_one_missing_value_is_off(self, configured, missing):
        """All three or nothing: two of them cannot reach a project."""
        assert configured.model_copy(update=missing).is_configured is False

    def test_all_three_is_on(self, configured):
        assert configured.is_configured is True


class TestConfigure:
    def test_unconfigured_attaches_no_handler(self, unconfigured):
        Tracing.configure(unconfigured)

        assert Tracing.enabled() is False
        assert Tracing.callbacks() == []

    def test_unconfigured_still_builds_a_client(self, unconfigured):
        """`@observe` calls `get_client()`; without one it builds a throwaway."""
        Tracing.configure(unconfigured)

        assert Tracing._client is not None

    def test_a_second_call_is_ignored(self, unconfigured, configured):
        """The SDK caches its client per key, so the first call is the one."""
        Tracing.configure(unconfigured)
        Tracing.configure(configured)

        assert Tracing.enabled() is False


class TestAttributes:
    def test_nothing_while_disabled(self, unconfigured):
        Tracing.configure(unconfigured)

        assert Tracing.attributes("flow-1") == {}

    def test_no_session_is_no_attribute(self, monkeypatch):
        """An unsessioned call is a trace of its own, not one keyed on ''."""
        monkeypatch.setattr(Tracing, "_enabled", True)

        assert Tracing.attributes("") == {}

    def test_a_session_groups_the_trace(self, monkeypatch):
        monkeypatch.setattr(Tracing, "_enabled", True)

        assert Tracing.attributes("flow-1") == {SESSION_KEY: "flow-1"}


class TestRecord:
    """Tests for naming what an `@observe` span was asked and answered."""

    def test_nothing_is_sent_while_disabled(self, unconfigured, mocker):
        """The suite runs untraced; a record here must reach no client."""
        Tracing.configure(unconfigured)
        update = mocker.patch.object(Tracing._client, "update_current_span")

        Tracing.record(asked={"prompt": "jazz"}, answered={"title": "Jazz"})

        update.assert_not_called()

    def test_both_ends_reach_the_span(self, mocker, monkeypatch):
        client = mocker.Mock()
        monkeypatch.setattr(Tracing, "_enabled", True)
        monkeypatch.setattr(Tracing, "_client", client)

        Tracing.record(asked={"prompt": "jazz"}, answered={"title": "Jazz"})

        client.update_current_span.assert_called_once_with(
            input={"prompt": "jazz"}, output={"title": "Jazz"}
        )

    def test_one_end_at_a_time_leaves_the_other_alone(self, mocker, monkeypatch):
        """A stream knows its input at the start and its output at the end."""
        client = mocker.Mock()
        monkeypatch.setattr(Tracing, "_enabled", True)
        monkeypatch.setattr(Tracing, "_client", client)

        Tracing.record(asked={"prompt": "jazz"})

        client.update_current_span.assert_called_once_with(input={"prompt": "jazz"}, output=None)


class TestShutdown:
    def test_shutdown_without_a_client_is_quiet(self):
        Tracing.shutdown()

        assert Tracing.enabled() is False

    def test_shutdown_drops_the_client(self, unconfigured):
        Tracing.configure(unconfigured)
        Tracing.shutdown()

        assert Tracing._client is None
