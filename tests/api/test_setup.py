"""Tests for setup/onboarding endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.config import (
    LLM_SECTION_ADAPTER,
    BudgetConfig,
    DefaultsConfig,
    MediasageConfig,
    PlexConfig,
)
from backend.library import SyncStatus
from tests.api.conftest import plex_store_of


@pytest.fixture
def client():
    """Create test client with mocked dependencies.

    Patches lifespan-triggered side effects (config loading, Plex/LLM init,
    library cache DB creation) so tests don't depend on real environment.
    """
    from backend.api import create_app

    with (
        patch("backend.config.store.ConfigStore.get", return_value=create_mock_config()),
        patch("backend.api.guards.init_llm"),
        patch("backend.api.routes.setup.library"),
        patch("backend.api.app.upgrade_to_head"),
    ):
        return TestClient(create_app())


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

    def test_status_returns_all_fields(self, client, tmp_path):
        """Should return full checklist state."""
        mock_plex = MagicMock()
        mock_plex.is_connected.return_value = True
        mock_plex.error = None
        mock_plex.music_libraries.return_value = ["Music"]

        with (
            patch("backend.config.store.ConfigStore.get", return_value=create_mock_config()),
            patch("backend.api.guards.plex_store", plex_store_of(mock_plex)),
            patch("backend.api.routes.setup.library") as mock_library,
            patch("backend.api.routes.setup.DATA_DIR", tmp_path),
            patch("backend.config.store.ConfigStore.read_user_yaml", return_value={}),
        ):
            mock_library.has_tracks.return_value = True
            mock_library.sync_status.return_value = SyncStatus(
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
        assert data["setup_complete"] is False
        assert data["music_libraries"] == ["Music"]

    def test_status_unconfigured(self, client, tmp_path):
        """Should show all steps incomplete when nothing is configured."""
        with (
            patch("backend.config.store.ConfigStore.get", return_value=create_mock_config(
                plex_url="", plex_token="", llm_api_key=""
            )),
            patch("backend.api.guards.plex_store", plex_store_of(None)),
            patch("backend.api.routes.setup.library") as mock_library,
            patch("backend.api.routes.setup.DATA_DIR", tmp_path),
            patch("backend.config.store.ConfigStore.read_user_yaml", return_value={}),
        ):
            mock_library.has_tracks.return_value = False
            mock_library.sync_status.return_value = SyncStatus(
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
        assert data["setup_complete"] is False

    def test_status_setup_complete(self, client, tmp_path):
        """Should reflect setup_complete from config.user.yaml."""
        with (
            patch("backend.config.store.ConfigStore.get", return_value=create_mock_config()),
            patch("backend.api.guards.plex_store", plex_store_of(None)),
            patch("backend.api.routes.setup.library") as mock_library,
            patch("backend.api.routes.setup.DATA_DIR", tmp_path),
            patch("backend.config.store.ConfigStore.read_user_yaml", return_value={"setup": {"complete": True}}),
        ):
            mock_library.has_tracks.return_value = False
            mock_library.sync_status.return_value = SyncStatus(
                track_count=0, synced_at=None, is_syncing=False, sync_progress=None, error=None
            )

            response = client.get("/api/setup/status")

        assert response.status_code == 200
        assert response.json()["setup_complete"] is True


class TestSetupValidatePlex:
    """Tests for POST /api/setup/validate-plex."""

    def test_validate_plex_success(self, client):
        """Should return success when Plex connects."""
        mock_temp_client = MagicMock()
        mock_temp_client.is_connected.return_value = True
        mock_temp_client.music_libraries.return_value = ["Music", "Audiobooks"]
        mock_temp_client.server_name = "My Plex Server"

        with (
            patch("backend.api.routes.setup.PlexClient.of", return_value=mock_temp_client),
            patch("backend.api.guards.plex_store", plex_store_of(None)),
            patch("backend.config.store.ConfigStore.apply"),
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
        mock_temp_client.is_connected.return_value = False
        mock_temp_client.error = "Invalid Plex token - unauthorized"

        with patch("backend.api.routes.setup.PlexClient.of", return_value=mock_temp_client):
            response = client.post("/api/setup/validate-plex", json={
                "plex_url": "http://plex:32400",
                "plex_token": "bad-token",
                "music_library": "Music",
            })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "unauthorized" in data["error"].lower()


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
            patch("backend.api.routes.setup.LLMClient") as mock_client,
            patch(
                "backend.config.store.ConfigStore.apply",
                return_value=create_mock_config(),
            ),
            patch("backend.api.guards.init_llm"),
        ):
            mock_client.return_value.complete.return_value = MagicMock(content="ok")
            response = client.post("/api/setup/validate-ai", json=self._payload())

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Anthropic" in data["provider_name"]

    def test_a_local_provider_validates_through_the_same_path(self, client):
        """No per-provider branch: a local endpoint is probed like any other."""
        with (
            patch("backend.api.routes.setup.LLMClient") as mock_client,
            patch(
                "backend.config.store.ConfigStore.apply",
                return_value=create_mock_config(llm_provider="ollama"),
            ),
            patch("backend.api.guards.init_llm"),
        ):
            mock_client.return_value.complete.return_value = MagicMock(content="ok")
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
        with patch("backend.api.routes.setup.LLMClient") as mock_client:
            mock_client.return_value.complete.side_effect = RuntimeError("nope")
            response = client.post("/api/setup/validate-ai", json=self._payload())

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] is not None

    def test_an_unauthorised_key_says_so(self, client):
        """A 401 is turned into something a setup form can show."""
        with patch("backend.api.routes.setup.LLMClient") as mock_client:
            mock_client.return_value.complete.side_effect = RuntimeError(
                "Error code: 401 - Unauthorized"
            )
            response = client.post("/api/setup/validate-ai", json=self._payload())

        assert response.json()["error"] == "Invalid API key"

    def test_validate_unknown_provider(self, client):
        """Should reject unknown providers."""
        response = client.post(
            "/api/setup/validate-ai", json=self._payload(provider="nonexistent")
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Unknown provider" in data["error"]

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


class TestSetupComplete:
    """Tests for POST /api/setup/complete."""

    def test_complete_saves_flag(self, client):
        """Should save setup.complete to config.user.yaml."""
        with patch("backend.config.store.ConfigStore.save") as mock_save:
            response = client.post("/api/setup/complete")

        assert response.status_code == 200
        assert response.json()["success"] is True
        mock_save.assert_called_once_with({"setup": {"complete": True}})

    def test_complete_handles_save_error(self, client):
        """Should still return success even if save fails (best-effort)."""
        with patch("backend.config.store.ConfigStore.save", side_effect=Exception("disk full")):
            response = client.post("/api/setup/complete")

        assert response.status_code == 200
        assert response.json()["success"] is True
