"""Tests for turning one configuration into chat models."""

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import SecretStr

from backend.config import CloudLLMConfig, LocalLLMConfig
from backend.llm import PROVIDER_IDS, ChatModels, LLMError
from backend.llm.constants import PLACEHOLDER_API_KEY


def chat_model(mocker) -> BaseChatModel:
    """A stand-in that passes the guard on what LangChain handed back."""
    return mocker.Mock(spec=BaseChatModel)


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


class TestKwargs:
    """Tests for the arguments handed to every integration."""

    def test_passes_the_configured_limits(self, cloud_config: CloudLLMConfig):
        kwargs = ChatModels(config=cloud_config).kwargs()

        assert kwargs["timeout"] == cloud_config.request_timeout
        assert kwargs["max_tokens"] == cloud_config.max_output_tokens
        assert kwargs["max_retries"] == cloud_config.max_retries

    def test_cloud_carries_no_base_url(self, cloud_config: CloudLLMConfig):
        """A hosted provider's endpoint is the integration's own."""
        assert "base_url" not in ChatModels(config=cloud_config).kwargs()

    def test_local_carries_the_endpoint(self, local_config: LocalLLMConfig):
        kwargs = ChatModels(config=local_config).kwargs()

        assert kwargs["base_url"] == "http://localhost:1234/v1"

    def test_local_substitutes_a_placeholder_key(self, local_config: LocalLLMConfig):
        """OpenAI-compatible servers reject an empty key even when they ignore it."""
        assert ChatModels(config=local_config).kwargs()["api_key"] == PLACEHOLDER_API_KEY

    def test_a_configured_local_key_is_kept(self, local_config: LocalLLMConfig):
        """Some local gateways do check it."""
        config = local_config.model_copy(update={"api_key": SecretStr("real-key")})

        assert ChatModels(config=config).kwargs()["api_key"] == "real-key"


class TestModelSelection:
    """Tests for which model answers to which role."""

    def test_analysis_uses_the_analysis_model(self, cloud_config: CloudLLMConfig):
        assert ChatModels(config=cloud_config).name_for("analysis") == "claude-sonnet-4-5"

    def test_generation_uses_the_generation_model(self, cloud_config: CloudLLMConfig):
        assert ChatModels(config=cloud_config).name_for("generation") == "claude-haiku-4-5"

    def test_smart_generation_swaps_in_the_analysis_model(self, cloud_config: CloudLLMConfig):
        """The whole point of the flag: pay more, generate better."""
        config = cloud_config.model_copy(update={"smart_generation": True})

        assert ChatModels(config=config).name_for("generation") == "claude-sonnet-4-5"

    def test_an_unconfigured_model_fails_loudly(self, cloud_config: CloudLLMConfig):
        """Better a named error than a provider rejecting an empty model."""
        config = cloud_config.model_copy(update={"model_analysis": ""})

        with pytest.raises(LLMError, match="No analysis model configured"):
            ChatModels(config=config).for_role("analysis")

    def test_a_built_model_is_reused(self, cloud_config: CloudLLMConfig, mocker):
        """Building one opens a client; a round spends the same role repeatedly."""
        built = mocker.patch("backend.llm.chat.init_chat_model", return_value=chat_model(mocker))
        models = ChatModels(config=cloud_config)

        models.for_role("analysis")
        models.for_role("analysis")

        built.assert_called_once()

    def test_each_role_is_built_separately(self, cloud_config: CloudLLMConfig, mocker):
        built = mocker.patch("backend.llm.chat.init_chat_model", return_value=chat_model(mocker))
        models = ChatModels(config=cloud_config)

        models.for_role("analysis")
        models.for_role("generation")

        assert built.call_count == 2

    def test_the_provider_id_reaches_langchain(self, local_config: LocalLLMConfig, mocker):
        built = mocker.patch("backend.llm.chat.init_chat_model", return_value=chat_model(mocker))

        ChatModels(config=local_config).for_role("analysis")

        assert built.call_args.kwargs["model_provider"] == "openai"

    def test_something_that_is_not_a_chat_model_fails_loudly(
        self, cloud_config: CloudLLMConfig, mocker
    ):
        """A LangChain change that widens the return must not reach `invoke`."""
        mocker.patch("backend.llm.chat.init_chat_model", return_value=object())

        with pytest.raises(LLMError, match="built no chat model"):
            ChatModels(config=cloud_config).for_role("analysis")
