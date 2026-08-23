"""Tests for the Ollama administrative client."""

import httpx
import ollama
import pytest
from ollama._types import ModelDetails

from backend.config import LocalLLMConfig, config_store
from backend.llm import OllamaClient


@pytest.fixture
def client() -> OllamaClient:
    return OllamaClient(base_url="http://localhost:11434", timeout=5.0)


def listing(*names: str) -> ollama.ListResponse:
    """A `/api/tags` response naming the given models."""
    return ollama.ListResponse(
        models=[
            ollama.ListResponse.Model(model=name, size=1024, modified_at=None) for name in names
        ]
    )


def shown(**fields) -> ollama.ShowResponse:
    """A `/api/show` response with the given fields."""
    return ollama.ShowResponse(**fields)


class TestListModels:
    """Tests for model discovery."""

    def test_maps_the_sdk_response(self, client, mocker):
        """Names and sizes come through onto our own model."""
        mocker.patch.object(ollama.Client, "list", return_value=listing("llama3:8b"))

        result = client.list_models()

        assert result.error is None
        assert [m.name for m in result.models] == ["llama3:8b"]

    def test_reports_an_unreachable_server(self, client, mocker):
        """A connection refused is an expected answer, not a fault."""
        mocker.patch.object(ollama.Client, "list", side_effect=httpx.ConnectError("refused"))

        result = client.list_models()

        assert "Cannot reach Ollama" in (result.error or "")
        assert result.models == []

    def test_reports_a_timeout_distinctly(self, client, mocker):
        """A slow server and a missing one need different messages."""
        mocker.patch.object(ollama.Client, "list", side_effect=httpx.TimeoutException("slow"))

        assert "Timeout" in (client.list_models().error or "")


class TestContextWindow:
    """Tests for reading a model's context window."""

    def test_reads_the_native_length(self):
        """The architecture key names the window the model was trained with."""
        payload = shown(model_info={"qwen3.context_length": 40960})

        assert OllamaClient.context_window_of(payload) == 40960

    def test_num_ctx_overrides_the_native_length(self):
        """An explicit num_ctx is what the server will actually allocate."""
        payload = shown(
            model_info={"llama.context_length": 131072},
            parameters="num_ctx                8192",
        )

        assert OllamaClient.context_window_of(payload) == 8192

    def test_returns_none_when_nothing_declares_a_window(self):
        """No guess: the caller asks the user instead of inventing 32768."""
        assert OllamaClient.context_window_of(shown(model_info={})) is None

    def test_ignores_a_non_integer_context_length(self):
        """A string where a count belongs is not a window."""
        payload = shown(model_info={"x.context_length": "big"})

        assert OllamaClient.context_window_of(payload) is None


class TestModelInfo:
    """Tests for describing one model."""

    def test_returns_none_for_an_unknown_model(self, client, mocker):
        """A 404 means the model is not pulled, which is not an error to log."""
        error = ollama.ResponseError("not found", status_code=404)
        mocker.patch.object(ollama.Client, "show", side_effect=error)

        assert client.model_info("nope") is None

    def test_carries_the_parameter_size(self, client, mocker):
        """The size is shown in the settings UI beside the name."""
        payload = shown(
            model_info={"llama.context_length": 8192},
            details=ModelDetails(parameter_size="8B"),
        )
        mocker.patch.object(ollama.Client, "show", return_value=payload)

        info = client.model_info("llama3:8b")

        assert info is not None
        assert info.parameter_size == "8B"
        assert info.context_window == 8192


class TestStatus:
    """Tests for the liveness probe."""

    def test_connected_with_models(self, client, mocker):
        mocker.patch.object(ollama.Client, "list", return_value=listing("a", "b"))

        result = client.status()

        assert result.connected is True
        assert result.model_count == 2
        assert result.error is None

    def test_connected_but_empty_says_what_to_do(self, client, mocker):
        """Reachable with nothing pulled is a distinct, actionable state."""
        mocker.patch.object(ollama.Client, "list", return_value=listing())

        result = client.status()

        assert result.connected is True
        assert "ollama pull" in (result.error or "")

    def test_unreachable_is_not_connected(self, client, mocker):
        mocker.patch.object(ollama.Client, "list", side_effect=httpx.ConnectError("refused"))

        assert client.status().connected is False


class TestConfigured:
    """The factory the settings routes build a client with."""

    @staticmethod
    def endpointed(monkeypatch, url: str) -> None:
        """Install a configuration naming `url` as the local Ollama server."""
        current = config_store.get()
        llm = LocalLLMConfig(
            provider="ollama", endpoint_url=url, context_window=current.llm.context_window
        )
        monkeypatch.setattr(config_store, "config", current.model_copy(update={"llm": llm}))

    def test_it_falls_back_to_the_configured_endpoint(self, monkeypatch, installed_config):
        self.endpointed(monkeypatch, "http://nas:11434")

        assert OllamaClient.configured().base_url == "http://nas:11434"

    def test_a_typed_url_wins_over_the_saved_one(self, monkeypatch, installed_config):
        """The wizard probes an endpoint before it has been saved."""
        self.endpointed(monkeypatch, "http://nas:11434")

        assert OllamaClient.configured("http://typed:11434").base_url == "http://typed:11434"

    def test_a_hosted_provider_offers_no_endpoint(self, installed_config):
        """There is nothing to probe until the form supplies a URL."""
        assert OllamaClient.configured().base_url == ""
