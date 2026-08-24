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


class TestSampling:
    """Tests for the sampling knobs, which are the model's to choose."""

    def test_nothing_is_sent_when_nothing_is_set(self, cloud_config: CloudLLMConfig):
        """An unset knob leaves the server's own default in force."""
        kwargs = ChatModels(config=cloud_config).kwargs()

        for knob in ("temperature", "top_p", "model_kwargs"):
            assert knob not in kwargs

    @pytest.mark.parametrize(("knob", "value"), [("temperature", 0.7), ("top_p", 0.8)])
    def test_the_universal_knobs_are_constructor_arguments(
        self, cloud_config: CloudLLMConfig, knob: str, value: float
    ):
        """Every integration takes these two by name."""
        config = cloud_config.model_copy(update={knob: value})

        assert ChatModels(config=config).kwargs()[knob] == value

    @pytest.mark.parametrize(
        ("knob", "value"),
        [("top_k", 20), ("min_p", 0.0), ("presence_penalty", 1.5), ("repetition_penalty", 1.0)],
    )
    def test_the_rest_reach_the_server_in_the_body(
        self, local_config: LocalLLMConfig, knob: str, value: float
    ):
        """No integration takes these by name, so they go through `model_kwargs`."""
        config = local_config.model_copy(update={knob: value})

        kwargs = ChatModels(config=config).kwargs()

        assert kwargs["model_kwargs"] == {knob: value}
        assert knob not in kwargs

    def test_a_whole_profile_is_carried(self, local_config: LocalLLMConfig):
        """A full set off a model card, which is how these arrive."""
        config = local_config.model_copy(
            update={
                "temperature": 0.7,
                "top_p": 0.80,
                "top_k": 20,
                "min_p": 0.0,
                "presence_penalty": 1.5,
                "repetition_penalty": 1.0,
            }
        )

        kwargs = ChatModels(config=config).kwargs()

        assert kwargs["temperature"] == 0.7
        assert kwargs["top_p"] == 0.80
        assert kwargs["model_kwargs"] == {
            "top_k": 20,
            "min_p": 0.0,
            "presence_penalty": 1.5,
            "repetition_penalty": 1.0,
        }


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
