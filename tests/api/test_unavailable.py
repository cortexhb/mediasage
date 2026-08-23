"""Tests for what every endpoint answers when a dependency is not configured.

Fifteen routes used to answer this by hand. Now each depends on the thing it
needs and one handler turns the failure into a 503, so each route is asserted
here to prove it still answers the same status.

Nothing is overridden: these exercise the real dependencies against empty
stores, which is the state a fresh install is in.
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.llm import LLMClientStore
from backend.plex import PlexClientStore
from tests.api.conftest import mediasage_config

# Every route that cannot run without a connected Plex server.
NEEDS_PLEX = (
    ("GET", "/api/library/stats"),
    ("GET", "/api/library/search?q=test"),
    ("POST", "/api/library/sync"),
    ("GET", "/api/plex/clients"),
    ("GET", "/api/plex/playlists"),
    ("GET", "/api/art/1"),
)

# Every route that cannot run without a configured model.
NEEDS_LLM = (
    ("POST", "/api/recommend/questions", {"prompt": "test"}),
    ("POST", "/api/recommend/switch-mode", {"session_id": "unknown", "mode": "discovery"}),
    ("POST", "/api/recommend/generate", {"session_id": "unknown", "answers": []}),
)


@pytest.fixture
def nothing_configured():
    """No Plex, no LLM, no pipeline -- what a fresh install looks like."""
    with (
        patch.object(PlexClientStore, "get", return_value=None),
        patch.object(LLMClientStore, "get", return_value=None),
        patch("backend.config.store.ConfigStore.get", return_value=mediasage_config()),
    ):
        yield


@pytest.fixture
def disconnected_plex():
    """A Plex client that exists but cannot reach its server."""
    plex = MagicMock()
    plex.connection.is_connected.return_value = False
    with patch.object(PlexClientStore, "get", return_value=plex):
        yield plex


class TestPlexGuard:
    @pytest.mark.parametrize(("method", "path"), NEEDS_PLEX)
    def test_missing_plex_is_503(self, client, nothing_configured, method, path):
        assert client.request(method, path).status_code == 503

    @pytest.mark.parametrize(("method", "path"), NEEDS_PLEX)
    def test_disconnected_plex_is_503(self, client, disconnected_plex, method, path):
        """A client that exists but cannot reach its server is not usable."""
        assert client.request(method, path).status_code == 503

    def test_the_message_says_which_dependency(self, client, nothing_configured):
        assert client.get("/api/library/stats").json()["detail"] == "Plex not connected"


class TestLLMGuard:
    @pytest.mark.parametrize(("method", "path", "body"), NEEDS_LLM)
    def test_missing_llm_is_503(self, client, nothing_configured, method, path, body):
        assert client.request(method, path, json=body).status_code == 503

    def test_the_message_says_which_dependency(self, client, nothing_configured):
        response = client.post("/api/recommend/questions", json={"prompt": "test"})
        assert "not configured" in response.json()["detail"]


class TestDegrading:
    def test_filter_analysis_returns_everything_without_an_llm(self, client, nothing_configured):
        """A failure here is not worth blocking on: the user narrows by hand."""
        response = client.post(
            "/api/recommend/analyze-prompt",
            json={"prompt": "test", "genres": ["Rock", "Jazz"], "decades": ["1990s"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["genres"] == ["Rock", "Jazz"]
        assert data["decades"] == ["1990s"]

    def test_health_answers_with_nothing_configured(self, client, nothing_configured):
        assert client.get("/api/health").status_code == 200

    def test_library_status_answers_with_no_plex(self, client, nothing_configured, temp_db):
        """The UI polls this to find out there is nothing to poll about."""
        response = client.get("/api/library/status")

        assert response.status_code == 200
        assert response.json()["plex_connected"] is False
