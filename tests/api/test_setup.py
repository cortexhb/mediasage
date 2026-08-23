"""Tests for setup/onboarding endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.config import (
    LLM_SECTION_ADAPTER,
    BudgetConfig,
    DefaultsConfig,
    MediasageConfig,
    PlexConfig,
)
from backend.library import SyncStatus
from tests.api.conftest import serve_live_config, serve_plex


@pytest.fixture
def client(monkeypatch):
    """A client over a freshly built application, with Plex unconfigured.

    Nothing is patched while the app is built: a route module imported under a
    patched `ConfigStore.get` would bind the mock as its dependency, and
    FastAPI would then ask the request for the mock's own arguments.
    """
    built = TestClient(create_app())
    serve_live_config(built.app)
    serve_plex(built.app, monkeypatch, None)
    return built


# Local providers need an endpoint; cloud ones must not carry one.
LOCAL_PROVIDERS = ("ollama", "custom")


def create_mock_config(**overrides) -> MediasageConfig:
    """Build a real config for setup tests, so arithmetic on it works."""
    defaults = {
        "plex_url": "http://test:32400",
        "plex_token": "token",
        "music_library": "Music",
        "llm_provider": "anthropic",
        "llm_api_key": "key",
        "model_analysis": "claude-sonnet-4-5",
        "model_generation": "claude-haiku-4-5",
        "endpoint_url": "http://localhost:11434",
        "context_window": 200_000,
    }
    defaults.update(overrides)

    llm = {
        "provider": defaults["llm_provider"],
        "api_key": defaults["llm_api_key"],
        "model_analysis": defaults["model_analysis"],
        "model_generation": defaults["model_generation"],
        "context_window": defaults["context_window"],
    }
    if defaults["llm_provider"] in LOCAL_PROVIDERS:
        llm["endpoint_url"] = defaults["endpoint_url"]

    return MediasageConfig(
        plex=PlexConfig(
            url=defaults["plex_url"],
            token=defaults["plex_token"],
            music_library=defaults["music_library"],
        ),
        llm=LLM_SECTION_ADAPTER.validate_python(llm),
        budget=BudgetConfig(),
        defaults=DefaultsConfig(track_count=25),
    )


class TestSetupStatus:
    """Tests for GET /api/setup/status."""

    def test_status_returns_all_fields(self, client, tmp_path, monkeypatch):
        """Should return full checklist state."""
        mock_plex = MagicMock()
        mock_plex.connection.is_connected.return_value = True
        mock_plex.connection.error = None
        mock_plex.connection.music_libraries.return_value = ["Music"]
        serve_plex(client.app, monkeypatch, mock_plex)

        with (
            patch("backend.config.store.ConfigStore.get", return_value=create_mock_config()),
            patch("backend.api.routes.setup.status.library") as mock_library,
            patch("backend.db.engine.DATA_DIR", tmp_path),
        ):
            mock_library.library_sync.has_tracks.return_value = True
            mock_library.library_sync.status.return_value = SyncStatus(
                track_count=1000,
                synced_at="2026-01-01T00:00:00",
                is_syncing=False,
            )

            response = client.get("/api/setup/status")

        assert response.status_code == 200
        data = response.json()
        assert data["plex_connected"] is True
        assert data["llm_configured"] is True
        assert data["library_synced"] is True
        assert data["track_count"] == 1000
        assert data["music_libraries"] == ["Music"]

    def test_status_unconfigured(self, client, tmp_path):
        """Should show all steps incomplete when nothing is configured."""
        with (
            patch("backend.config.store.ConfigStore.get", return_value=create_mock_config(
                plex_url="", plex_token="", llm_api_key=""
            )),
            patch("backend.api.routes.setup.status.library") as mock_library,
            patch("backend.db.engine.DATA_DIR", tmp_path),
        ):
            mock_library.library_sync.has_tracks.return_value = False
            mock_library.library_sync.status.return_value = SyncStatus(
                track_count=0,
                synced_at=None,
                is_syncing=False,
                sync_progress=None,
            )

            response = client.get("/api/setup/status")

        assert response.status_code == 200
        data = response.json()
        assert data["plex_connected"] is False
        assert data["llm_configured"] is False
        assert data["library_synced"] is False


class TestSetupValidatePlex:
    """Tests for POST /api/setup/validate-plex."""

    def test_validate_plex_success(self, client):
        """Should return success when Plex connects."""
        mock_temp_client = MagicMock()
        mock_temp_client.connection.is_connected.return_value = True
        mock_temp_client.connection.music_libraries.return_value = ["Music", "Audiobooks"]
        mock_temp_client.connection.server_name = "My Plex Server"

        with (
            patch("backend.api.probes.PlexClient.of", return_value=mock_temp_client),
            patch("backend.config.store.ConfigStore.commit"),
        ):
            response = client.post("/api/setup/validate-plex", json={
                "plex_url": "http://plex:32400",
                "plex_token": "abc123",
                "music_library": "Music",
            })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["server_name"] == "My Plex Server"
        assert data["music_libraries"] == ["Music", "Audiobooks"]

    def test_validate_plex_failure(self, client):
        """Should return error when Plex connection fails."""
        mock_temp_client = MagicMock()
        mock_temp_client.connection.is_connected.return_value = False
        mock_temp_client.connection.error = "Invalid Plex token - unauthorized"

        with patch("backend.api.probes.PlexClient.of", return_value=mock_temp_client):
            response = client.post("/api/setup/validate-plex", json={
                "plex_url": "http://plex:32400",
                "plex_token": "bad-token",
                "music_library": "Music",
            })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "unauthorized" in data["error"].lower()


    def test_a_refused_server_saves_nothing(self, client):
        """A credential the wizard could not prove must not reach disk."""
        refused = MagicMock()
        refused.connection.is_connected.return_value = False
        refused.connection.error = "Invalid Plex token - unauthorized"

        with (
            patch("backend.api.probes.PlexClient.of", return_value=refused),
            patch("backend.config.store.ConfigStore.commit") as commit,
        ):
            client.post("/api/setup/validate-plex", json={
                "plex_url": "http://plex:32400",
                "plex_token": "bad-token",
                "music_library": "Music",
            })

        commit.assert_not_called()

    def test_the_merged_candidate_is_probed_not_the_form(self, client):
        """A wizard field is one part of a section; the rest still applies."""
        config = create_mock_config()
        tuned = config.model_copy(update={"plex": config.plex.model_copy(update={"page_size": 250})})
        answering = MagicMock()
        answering.connection.server_name = "My Plex Server"
        answering.connection.is_connected.return_value = True
        answering.connection.music_libraries.return_value = ["Music"]

        with (
            patch("backend.config.store.ConfigStore.get", return_value=tuned),
            patch("backend.api.probes.PlexClient") as build,
            patch("backend.config.store.ConfigStore.commit", return_value=tuned),
        ):
            build.of.return_value = answering
            client.post("/api/setup/validate-plex", json={
                "plex_url": "http://plex:32400",
                "plex_token": "abc123",
                "music_library": "Music",
            })

        probed = build.of.call_args.args[0]
        assert (probed.url, probed.page_size) == ("http://plex:32400", 250)


class TestSetupValidateAI:
    """Tests for POST /api/setup/validate-ai.

    Validation is one real completion through LangChain, the same path the app
    uses, so a provider that answers here is a provider that will answer later.
    """

    def _payload(self, **overrides) -> dict:
        return {
            "provider": "anthropic",
            "api_key": "test-key",
            "model": "claude-haiku-4-5",
            "context_window": 200_000,
        } | overrides

    def test_a_reachable_provider_validates(self, client):
        """A successful completion is the whole test."""
        with (
            patch("backend.api.probes.LLMClient") as mock_client,
            patch(
                "backend.config.store.ConfigStore.commit",
                return_value=create_mock_config(),
            ),
        ):
            mock_client.of.return_value.complete.return_value = MagicMock(content="ok")
            response = client.post("/api/setup/validate-ai", json=self._payload())

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Anthropic" in data["provider_name"]

    def test_a_local_provider_validates_through_the_same_path(self, client):
        """No per-provider branch: a local endpoint is probed like any other."""
        with (
            patch("backend.api.probes.LLMClient") as mock_client,
            patch(
                "backend.config.store.ConfigStore.commit",
                return_value=create_mock_config(llm_provider="ollama"),
            ),
        ):
            mock_client.of.return_value.complete.return_value = MagicMock(content="ok")
            response = client.post(
                "/api/setup/validate-ai",
                json=self._payload(
                    provider="ollama",
                    endpoint_url="http://localhost:11434",
                    model="llama3",
                    context_window=8192,
                ),
            )

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_a_failing_provider_is_reported(self, client):
        """Whatever the provider raises becomes the form's error."""
        with patch("backend.api.probes.LLMClient") as mock_client:
            mock_client.of.return_value.complete.side_effect = RuntimeError("nope")
            response = client.post("/api/setup/validate-ai", json=self._payload())

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] is not None

    def test_an_unauthorised_key_says_so(self, client):
        """A 401 is turned into something a setup form can show."""
        with patch("backend.api.probes.LLMClient") as mock_client:
            mock_client.of.return_value.complete.side_effect = RuntimeError(
                "Error code: 401 - Unauthorized"
            )
            response = client.post("/api/setup/validate-ai", json=self._payload())

        assert response.json()["error"] == "Invalid API key"

    def test_a_refused_provider_saves_nothing(self, client):
        with (
            patch("backend.api.probes.LLMClient") as mock_client,
            patch("backend.config.store.ConfigStore.commit") as commit,
        ):
            mock_client.of.return_value.complete.side_effect = RuntimeError("nope")
            client.post("/api/setup/validate-ai", json=self._payload())

        commit.assert_not_called()

    def test_validate_unknown_provider(self, client):
        """Should reject unknown providers."""
        response = client.post(
            "/api/setup/validate-ai", json=self._payload(provider="nonexistent")
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Unknown provider" in data["error"]
        # Echoed rather than mapped: the label map has no entry to give.
        assert data["provider_name"] == "nonexistent"

    def test_a_missing_model_is_rejected(self, client):
        """Nothing is guessed: a provider without a model cannot be probed."""
        response = client.post("/api/setup/validate-ai", json=self._payload(model=""))

        assert response.json()["success"] is False
        assert "model name is required" in response.json()["error"]

    def test_a_missing_context_window_is_rejected(self, client):
        """The window is required of every provider, so setup must collect it."""
        response = client.post(
            "/api/setup/validate-ai", json=self._payload(context_window=0)
        )

        assert response.json()["success"] is False
        assert "context window is required" in response.json()["error"]
