"""Tests for ``/api/config`` and ``/api/ollama``."""

from unittest.mock import MagicMock, patch

import pytest

from backend.config import ConfigSaveError
from backend.llm import OllamaModel, OllamaModelInfo, OllamaModelsResponse, OllamaStatus
from tests.api.conftest import mediasage_config

OLLAMA_CONFIG = mediasage_config(
    llm_provider="ollama", endpoint_url="http://localhost:11434"
)


@pytest.fixture
def ollama():
    """Patch the Ollama admin client and hand back the class mock."""
    with (
        patch("backend.config.store.ConfigStore.get", return_value=OLLAMA_CONFIG),
        patch("backend.api.routes.config.ollama.OllamaClient") as mock,
    ):
        # `configured` is the factory the routes call; make it hand back the
        # same instance mock, so a test can script a call without naming a URL.
        mock.configured.return_value = mock.return_value
        yield mock


class TestGetConfig:
    def test_returns_the_plex_url_but_never_the_token(self, client, plex):
        config = mediasage_config(plex_url="http://test:32400", plex_token="secret-token")
        with patch("backend.config.store.ConfigStore.get", return_value=config):
            response = client.get("/api/config")

        assert response.status_code == 200
        assert response.json()["plex_url"] == "http://test:32400"
        assert "secret-token" not in response.text

    def test_returns_the_provider_but_never_the_key(self, client, plex):
        config = mediasage_config(llm_provider="anthropic", llm_api_key="secret-api-key")
        with patch("backend.config.store.ConfigStore.get", return_value=config):
            response = client.get("/api/config")

        data = response.json()
        assert data["llm_provider"] == "anthropic"
        assert data["llm_api_key_set"] is True
        assert "api_key" not in data
        assert "secret-api-key" not in response.text

    def test_reports_the_prompt_budget(self, client, plex):
        """The UI shows how much of the library one prompt can carry."""
        with patch("backend.config.store.ConfigStore.get", return_value=mediasage_config()):
            data = client.get("/api/config").json()

        assert data["max_tracks_to_ai"] > 0
        assert data["max_albums_to_ai"] > 0


class TestUpdateConfig:
    """A change is proved, written, published, and then rebuilt."""

    def test_saves_a_new_plex_url(self, client, plex, answering):
        config = mediasage_config(plex_url="http://new-server:32400")
        with patch("backend.config.store.ConfigStore.commit", return_value=config):
            response = client.post("/api/config", json={"plex_url": "http://new-server:32400"})

        assert response.status_code == 200
        assert response.json()["plex_url"] == "http://new-server:32400"

    def test_saves_a_new_provider(self, client, plex, answering):
        config = mediasage_config(llm_provider="openai")
        with patch("backend.config.store.ConfigStore.commit", return_value=config):
            response = client.post("/api/config", json={"llm_provider": "openai"})

        assert response.status_code == 200
        assert response.json()["llm_provider"] == "openai"

    def test_a_plex_change_rebuilds_the_plex_client(self, client, plex, answering, rebuilds):
        """Without the rebuild the next request would use the old server."""
        config = mediasage_config()
        with (
            patch("backend.config.store.ConfigStore.commit", return_value=config),
        ):
            client.post("/api/config", json={"plex_url": "http://new:32400"})

        rebuilds.plex.assert_called_once_with(config.plex)

    def test_an_llm_change_rebuilds_the_llm_client(self, client, plex, answering, rebuilds):
        config = mediasage_config()
        with (
            patch("backend.config.store.ConfigStore.commit", return_value=config),
        ):
            client.post("/api/config", json={"llm_provider": "openai"})

        rebuilds.llm.assert_called_once_with(config.llm)

    def test_an_empty_update_is_rejected(self, client, plex):
        assert client.post("/api/config", json={}).status_code == 400


class TestUpdateConfigProbes:
    """Nothing is written until what the change could break has answered."""

    def test_a_plex_url_that_does_not_answer_is_refused(self, client, plex):
        refused = MagicMock()
        refused.connection.is_connected.return_value = False
        refused.connection.error = "Invalid Plex token - unauthorized"

        with (
            patch("backend.api.probes.PlexClient.of", return_value=refused),
            patch("backend.config.store.ConfigStore.commit") as commit,
        ):
            response = client.post("/api/config", json={"plex_url": "http://new:32400"})

        assert response.status_code == 422
        assert "unauthorized" in response.json()["detail"]
        commit.assert_not_called()

    def test_a_provider_that_does_not_answer_is_refused(self, client, plex):
        with (
            patch("backend.api.probes.LLMClient") as llm,
            patch("backend.config.store.ConfigStore.commit") as commit,
        ):
            llm.of.return_value.complete.side_effect = RuntimeError("nope")
            response = client.post("/api/config", json={"llm_provider": "openai"})

        assert response.status_code == 422
        commit.assert_not_called()

    def test_a_refused_change_rebuilds_nothing(self, client, plex, rebuilds):
        """The held client still works; replacing it with a broken one would help nobody."""
        refused = MagicMock()
        refused.connection.is_connected.return_value = False
        refused.connection.error = "unauthorized"

        with (
            patch("backend.api.probes.PlexClient.of", return_value=refused),
            patch("backend.config.store.ConfigStore.commit"),
        ):
            client.post("/api/config", json={"plex_url": "http://new:32400"})

        rebuilds.plex.assert_not_called()

    def test_a_price_edit_spends_no_completion(self, client, plex):
        """A number the UI reports back must not fail because a provider is down."""
        with (
            patch("backend.api.probes.LLMClient") as llm,
            patch("backend.api.probes.PlexClient") as plex_client,
            patch(
                "backend.config.store.ConfigStore.commit", return_value=mediasage_config()
            ),
        ):
            response = client.post("/api/config", json={"cost_analysis_input": 3.0})

        assert response.status_code == 200
        llm.of.assert_not_called()
        plex_client.of.assert_not_called()

    def test_a_failed_write_is_a_500(self, client, plex, answering):
        with patch(
            "backend.config.store.ConfigStore.commit",
            side_effect=ConfigSaveError("disk full"),
        ):
            response = client.post("/api/config", json={"plex_url": "http://new:32400"})

        assert response.status_code == 500


class TestOllama:
    def test_status_reports_a_reachable_server(self, client, ollama):
        ollama.return_value.status.return_value = OllamaStatus(connected=True, model_count=3)

        data = client.get("/api/ollama/status").json()

        assert data["connected"] is True
        assert data["model_count"] == 3

    def test_status_reports_an_unreachable_one(self, client, ollama):
        """A refused connection is a 200 with the reason; the form shows it."""
        ollama.return_value.status.return_value = OllamaStatus(
            connected=False, model_count=0, error="Connection refused"
        )

        data = client.get("/api/ollama/status").json()

        assert data["connected"] is False
        assert data["error"] == "Connection refused"

    def test_status_accepts_a_url_the_form_is_still_typing(self, client, ollama):
        """The wizard probes an endpoint before it has been saved."""
        ollama.return_value.status.return_value = OllamaStatus(connected=True, model_count=1)

        client.get("/api/ollama/status?url=http://custom-host:11434")

        assert ollama.configured.call_args.args == ("http://custom-host:11434",)

    def test_models_lists_what_is_pulled(self, client, ollama):
        ollama.return_value.list_models.return_value = OllamaModelsResponse(models=[
            OllamaModel(name="llama3:8b", size=4661224676, modified_at="2024-01-15T00:00:00Z"),
            OllamaModel(name="mistral:latest", size=3825819904, modified_at="2024-01-14T00:00:00Z"),
        ])

        data = client.get("/api/ollama/models").json()

        assert [model["name"] for model in data["models"]] == ["llama3:8b", "mistral:latest"]

    def test_model_info_reports_the_context_window(self, client, ollama):
        """The only place a context window is discovered rather than typed."""
        ollama.return_value.model_info.return_value = OllamaModelInfo(
            name="llama3:8b", context_window=8192, parameter_size="8B"
        )

        data = client.get("/api/ollama/model-info?model=llama3:8b").json()

        assert data["context_window"] == 8192

    def test_an_unknown_model_is_404(self, client, ollama):
        ollama.return_value.model_info.return_value = None

        assert client.get("/api/ollama/model-info?model=nonexistent").status_code == 404
