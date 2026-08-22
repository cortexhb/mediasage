"""Tests for the provider-neutral chat client."""

import pytest
from langchain_core.messages import AIMessage

from backend.config import CloudLLMConfig, LocalLLMConfig
from backend.llm import PROVIDER_IDS, LLMClient, LLMClientStore, LLMError
from backend.llm.constants import PLACEHOLDER_API_KEY


def reply(text: str = '{"ok": true}', **usage) -> AIMessage:
    """An AIMessage as a provider would return it."""
    counts = {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14} | usage
    return AIMessage(content=text, usage_metadata=counts)


class TestProviderMapping:
    """Tests for how our provider names reach LangChain."""

    def test_every_configurable_provider_is_mapped(self):
        """A provider the config accepts must be one the client can build."""
        from typing import get_args

        from backend.config import Provider

        assert set(PROVIDER_IDS) == set(get_args(Provider))

    def test_gemini_maps_to_google_genai(self):
        """Our name and LangChain's differ for exactly this one."""
        assert PROVIDER_IDS["gemini"] == "google_genai"

    def test_custom_is_openai_compatible(self):
        """A custom endpoint is reached with the OpenAI integration."""
        assert PROVIDER_IDS["custom"] == "openai"


class TestBuildKwargs:
    """Tests for the arguments handed to every integration."""

    def test_passes_the_configured_limits(self, cloud_config: CloudLLMConfig):
        """Timeout, output cap and retries all come from config."""
        kwargs = LLMClient(cloud_config).build_kwargs()

        assert kwargs["timeout"] == cloud_config.request_timeout
        assert kwargs["max_tokens"] == cloud_config.max_output_tokens
        assert kwargs["max_retries"] == cloud_config.max_retries

    def test_cloud_carries_no_base_url(self, cloud_config: CloudLLMConfig):
        """A hosted provider is reached at its own address."""
        assert "base_url" not in LLMClient(cloud_config).build_kwargs()

    def test_local_carries_the_endpoint(self, local_config: LocalLLMConfig):
        """A local provider is reached only by the configured URL."""
        kwargs = LLMClient(local_config).build_kwargs()

        assert kwargs["base_url"] == "http://localhost:1234/v1"

    def test_local_substitutes_a_placeholder_key(self, local_config: LocalLLMConfig):
        """OpenAI-compatible servers reject an empty key even when ignoring it."""
        assert LLMClient(local_config).build_kwargs()["api_key"] == PLACEHOLDER_API_KEY

    def test_a_configured_local_key_is_kept(self, local_config: LocalLLMConfig):
        """A key the user set must reach the endpoint."""
        config = local_config.model_copy(update={"api_key": "real-key"})

        assert LLMClient(config).build_kwargs()["api_key"] == "real-key"


class TestModelSelection:
    """Tests for which model a role spends."""

    def test_analysis_uses_the_analysis_model(self, cloud_config: CloudLLMConfig):
        assert LLMClient(cloud_config).model_name("analysis") == "claude-sonnet-4-5"

    def test_generation_uses_the_generation_model(self, cloud_config: CloudLLMConfig):
        assert LLMClient(cloud_config).model_name("generation") == "claude-haiku-4-5"

    def test_smart_generation_swaps_in_the_analysis_model(
        self, cloud_config: CloudLLMConfig
    ):
        """`smart_generation` buys quality by spending the expensive model."""
        config = cloud_config.model_copy(update={"smart_generation": True})

        assert LLMClient(config).model_name("generation") == "claude-sonnet-4-5"

    def test_an_unconfigured_model_fails_loudly(self, cloud_config: CloudLLMConfig):
        """Nothing is guessed in place of a model the user never named."""
        config = cloud_config.model_copy(update={"model_analysis": ""})

        with pytest.raises(LLMError, match="No analysis model"):
            LLMClient(config).model_for("analysis")


class TestComplete:
    """Tests for a single completion."""

    def _client(self, config, message: AIMessage, mocker) -> LLMClient:
        client = LLMClient(config)
        model = mocker.Mock()
        model.invoke.return_value = message
        mocker.patch.object(client, "model_for", return_value=model)
        return client

    def test_returns_the_providers_token_counts(self, cloud_config, mocker):
        """Counts are reported, not estimated."""
        client = self._client(cloud_config, reply(), mocker)

        response = client.analyze("prompt", "system")

        assert response.input_tokens == 10
        assert response.output_tokens == 4

    def test_tags_the_response_with_its_role(self, cloud_config, mocker):
        """The role decides which price applies later."""
        client = self._client(cloud_config, reply(), mocker)

        assert client.generate("p", "s").role == "generation"
        assert client.analyze("p", "s").role == "analysis"

    def test_sends_system_and_user_messages(self, cloud_config, mocker):
        """Both prompts must reach the model, in that order."""
        client = LLMClient(cloud_config)
        model = mocker.Mock()
        model.invoke.return_value = reply()
        mocker.patch.object(client, "model_for", return_value=model)

        client.analyze("the prompt", "the system")

        messages = model.invoke.call_args[0][0]
        assert messages[0].content == "the system"
        assert messages[1].content == "the prompt"

    def test_an_empty_reply_names_the_context_window(self, cloud_config, mocker):
        """The likely cause is a window too small, so the message says so."""
        client = self._client(cloud_config, reply(""), mocker)

        with pytest.raises(LLMError, match="200,000 tokens"):
            client.analyze("p", "s")

    def test_parses_json_out_of_the_reply(self, cloud_config, mocker):
        """The client hands back decoded JSON, fences and all."""
        client = self._client(cloud_config, reply('```json\n{"ok": true}\n```'), mocker)

        response = client.generate("p", "s")

        assert LLMClient.parse_json_response(response) == {"ok": True}


class TestClientStore:
    """Tests for the process-level client holder."""

    def test_starts_empty(self):
        """Nothing is built before a provider is configured."""
        assert LLMClientStore().get() is None

    def test_require_fails_loudly_when_unconfigured(self):
        """Callers that cannot proceed get an error, not a None to check."""
        with pytest.raises(LLMError, match="not configured"):
            LLMClientStore().require()

    def test_init_replaces_the_client(self, cloud_config, local_config):
        """A settings change must not leave the old client in place."""
        store = LLMClientStore()
        store.init(cloud_config)
        store.init(local_config)

        assert store.require().provider == "custom"
