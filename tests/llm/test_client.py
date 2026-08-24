"""Tests for the provider-neutral chat client."""

from unittest.mock import Mock

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage

from backend.cancellation import Abandoned, Cancellation
from backend.llm import LLMClient, LLMClientStore, LLMError
from backend.tracing import SESSION_KEY, Tracing


def reply(text: str = '{"ok": true}', **usage) -> AIMessage:
    """An AIMessage as a provider would return it."""
    counts = {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14} | usage
    return AIMessage(content=text, usage_metadata=counts)


class TestComplete:
    """Tests for a single completion."""

    def _client(self, config, message: AIMessage, mocker) -> tuple[LLMClient, Mock]:
        """A client whose every role resolves to one stubbed chat model."""
        model = mocker.Mock(spec=BaseChatModel)
        model.invoke.return_value = message
        mocker.patch("backend.llm.chat.init_chat_model", return_value=model)
        return LLMClient.of(config), model

    def test_returns_the_providers_token_counts(self, cloud_config, mocker):
        """Counts are reported, not estimated."""
        client, _ = self._client(cloud_config, reply(), mocker)

        response = client.analyze("prompt", "system")

        assert response.input_tokens == 10
        assert response.output_tokens == 4

    def test_tags_the_response_with_its_role(self, cloud_config, mocker):
        """The role decides which price applies later."""
        client, _ = self._client(cloud_config, reply(), mocker)

        assert client.generate("p", "s").role == "generation"
        assert client.analyze("p", "s").role == "analysis"

    def test_names_the_model_that_answered(self, cloud_config, mocker):
        client, _ = self._client(cloud_config, reply(), mocker)

        assert client.generate("p", "s").model == "claude-haiku-4-5"

    def test_sends_system_and_user_messages(self, cloud_config, mocker):
        """Both prompts must reach the model, in that order."""
        client, model = self._client(cloud_config, reply(), mocker)

        client.analyze("the prompt", "the system")

        messages = model.invoke.call_args[0][0]
        assert messages[0].content == "the system"
        assert messages[1].content == "the prompt"

    def test_an_empty_reply_names_the_context_window(self, cloud_config, mocker):
        """The likely cause is a window too small, so the message says so."""
        client, _ = self._client(cloud_config, reply(""), mocker)

        with pytest.raises(LLMError, match="200,000 tokens"):
            client.analyze("p", "s")

    def test_a_whitespace_only_reply_counts_as_empty(self, cloud_config, mocker):
        client, _ = self._client(cloud_config, reply("   \n  "), mocker)

        with pytest.raises(LLMError):
            client.analyze("p", "s")

    def test_nothing_is_sent_once_the_client_has_left(self, cloud_config, mocker):
        """A completion cannot be recalled, so the saving is not starting one."""
        client, model = self._client(cloud_config, reply(), mocker)
        Cancellation.watch().set()

        with pytest.raises(Abandoned):
            client.generate("p", "s")

        model.invoke.assert_not_called()

    def test_a_watched_run_still_completes(self, cloud_config, mocker):
        """Watching must cost the run nothing while its reader is there."""
        client, _ = self._client(cloud_config, reply(), mocker)
        Cancellation.watch()

        assert client.generate("p", "s").content


class TestTracing:
    """Tests for what the one place a prompt is sent hands to Langfuse."""

    def _client(self, config, mocker) -> tuple[LLMClient, Mock]:
        model = mocker.Mock(spec=BaseChatModel)
        model.invoke.return_value = reply()
        mocker.patch("backend.llm.chat.init_chat_model", return_value=model)
        return LLMClient.of(config), model

    def _config(self, model: Mock) -> dict:
        return model.invoke.call_args.kwargs["config"]

    def test_no_handler_while_tracing_is_off(self, cloud_config, mocker):
        """The suite runs untraced, and so does an unconfigured deployment."""
        client, model = self._client(cloud_config, mocker)

        client.analyze("p", "s")

        assert self._config(model)["callbacks"] == []

    def test_the_call_is_named_for_its_role(self, cloud_config, mocker):
        client, model = self._client(cloud_config, mocker)

        client.generate("p", "s")

        assert self._config(model)["run_name"] == "mediasage:generation-completion"

    def test_the_handler_is_attached_while_tracing_is_on(self, cloud_config, mocker, monkeypatch):
        monkeypatch.setattr(Tracing, "_enabled", True)
        client, model = self._client(cloud_config, mocker)

        client.analyze("p", "s")

        assert self._config(model)["callbacks"]

    def test_the_session_reaches_the_call(self, cloud_config, mocker, monkeypatch):
        """One flow's calls group into one Langfuse session."""
        monkeypatch.setattr(Tracing, "_enabled", True)
        client, model = self._client(cloud_config, mocker)

        client.analyze("p", "s", "flow-1")

        assert self._config(model)["metadata"] == {SESSION_KEY: "flow-1"}


class TestConfiguration:
    """Tests for what the client exposes about how it was built."""

    def test_it_reports_its_provider(self, local_config):
        assert LLMClient.of(local_config).provider == "custom"

    def test_it_hands_back_the_configuration_it_holds(self, cloud_config):
        """One config, one owner: the models hold it and the client reads it."""
        client = LLMClient.of(cloud_config)

        assert client.config is client.models.config is cloud_config


class TestClientStore:
    """Tests for the process-level client holder."""

    def test_starts_empty(self):
        """Nothing is built before a provider is configured."""
        assert LLMClientStore().get() is None

    def test_require_fails_loudly_when_unconfigured(self):
        """Callers that cannot proceed get an error, not a None to check."""
        with pytest.raises(LLMError, match="not configured"):
            LLMClientStore().require()

    def test_a_replaced_client_is_the_one_handed_back(self, cloud_config, local_config):
        """A settings change must not leave the old client in place."""
        store = LLMClientStore()
        store.client = LLMClient.of(cloud_config)
        store.client = LLMClient.of(local_config)

        assert store.require().provider == "custom"

    def test_the_held_client_is_the_one_handed_back(self, cloud_config):
        """`pipeline_store` rebuilds on identity, so this must not be a copy."""
        store = LLMClientStore()
        store.client = LLMClient.of(cloud_config)

        assert store.require() is store.get()
