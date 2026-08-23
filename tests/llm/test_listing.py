"""Tests for asking a provider which models it serves.

A listing never raises and never spends a completion: every way a provider can
refuse is an answer a settings form has to show. The seam is each provider's
own SDK, because that is what the app itself talks through.
"""

from typing import Literal
from unittest.mock import MagicMock, patch

import anthropic
import httpx
import openai
import pytest
from google.genai import errors as genai_errors

from backend.config import CloudLLMConfig, LocalLLMConfig
from backend.llm.listing import (
    LISTINGS,
    TIMEOUTS,
    AnthropicListing,
    GeminiListing,
    ListingRefused,
    ModelListing,
    OllamaListing,
    OpenAIListing,
)


def cloud(
    provider: Literal["anthropic", "openai", "gemini"] = "openai", **overrides
) -> CloudLLMConfig:
    """A hosted provider, keyed and reachable."""
    return CloudLLMConfig(provider=provider, api_key="sk-test", context_window=128_000, **overrides)


def local(
    provider: Literal["ollama", "custom"] = "custom",
    endpoint_url: str = "http://localhost:1234/v1",
    **overrides,
) -> LocalLLMConfig:
    """A server on the user's own hardware, reached by URL."""
    return LocalLLMConfig(
        provider=provider, endpoint_url=endpoint_url, context_window=32_768, **overrides
    )


def serving(*ids: str) -> MagicMock:
    """An SDK client whose `models.list()` answers with `ids`."""
    client = MagicMock()
    client.models.list.return_value = [MagicMock(id=model_id) for model_id in ids]
    return client


def answered(status: int) -> httpx.Response:
    return httpx.Response(
        status, json={"error": "refused"}, request=httpx.Request("GET", "http://x")
    )


def refused(status: int) -> anthropic.APIStatusError:
    """A real SDK failure, so `status_of` is tested against a client, not a stub.

    Anthropic's rather than OpenAI's: `openai` types itself against the separate
    `httpx2` package, so building its errors from `httpx` would not type-check.
    Both set `status_code`, which is the attribute under test.
    """
    return anthropic.APIStatusError("refused", response=answered(status), body=None)


def refused_by_google(status: int) -> genai_errors.ClientError:
    """Google's SDK carries `code` where the others carry `status_code`."""
    return genai_errors.ClientError(status, {"error": {"message": "refused"}}, answered(status))


class TestOpenAIListing:
    """OpenAI, and every OpenAI-compatible server."""

    def test_a_hosted_provider_leaves_the_sdk_its_own_base_url(self):
        """`None`, not "": the SDK default is what LangChain would use too."""
        with patch("openai.OpenAI", return_value=serving("gpt-4o")) as client:
            names = OpenAIListing().names(cloud())

        assert names == ("gpt-4o",)
        assert client.call_args.kwargs["base_url"] is None

    def test_a_local_server_is_asked_at_the_endpoint_the_app_uses(self):
        with patch("openai.OpenAI", return_value=serving("local-model")) as client:
            OpenAIListing().names(local())

        assert client.call_args.kwargs["base_url"] == "http://localhost:1234/v1"

    def test_a_keyless_local_server_still_receives_a_credential(self):
        """OpenAI-compatible servers reject an empty key even when they ignore it."""
        with patch("openai.OpenAI", return_value=serving()) as client:
            OpenAIListing().names(local())

        assert client.call_args.kwargs["api_key"] == "not-needed"

    def test_the_probe_timeout_bounds_the_call_and_retries_are_off(self):
        """Metadata: `request_timeout` and its retries would hang a save for minutes."""
        with patch("openai.OpenAI", return_value=serving()) as client:
            OpenAIListing().names(cloud(probe_timeout=2.5, request_timeout=600.0, max_retries=3))

        assert client.call_args.kwargs["timeout"] == 2.5
        assert client.call_args.kwargs["max_retries"] == 0


class TestAnthropicListing:
    def test_models_come_back_by_id(self):
        with patch("anthropic.Anthropic", return_value=serving("claude-haiku-4-5")) as client:
            names = AnthropicListing().names(cloud("anthropic"))

        assert names == ("claude-haiku-4-5",)
        assert client.call_args.kwargs["max_retries"] == 0


class TestGeminiListing:
    def test_names_lose_their_collection_prefix(self):
        listed = MagicMock()
        listed.models.list.return_value = [MagicMock(name="x")]
        listed.models.list.return_value[0].name = "models/gemini-2.0-flash"

        with patch("google.genai.Client", return_value=listed):
            names = GeminiListing().names(cloud("gemini"))

        assert names == ("gemini-2.0-flash",)

    def test_the_timeout_is_converted_to_milliseconds(self):
        """`HttpOptions.timeout` counts in ms; seconds would be a 2.5ms budget."""
        with patch("google.genai.Client", return_value=serving()) as client:
            GeminiListing().names(cloud("gemini", probe_timeout=2.5))

        assert client.call_args.kwargs["http_options"].timeout == 2500


class TestOllamaListing:
    def test_pulled_models_are_listed(self):
        listed = MagicMock(error="", models=[MagicMock(name="x")])
        listed.models[0].name = "llama3:latest"

        with patch("backend.llm.listing.OllamaClient") as client:
            client.return_value.list_models.return_value = listed
            names = OllamaListing().names(local("ollama", endpoint_url="http://localhost:11434"))

        assert names == ("llama3:latest",)

    def test_a_failure_carries_its_own_message(self):
        """`OllamaClient` already phrases these for a form; nothing re-words them."""
        with patch("backend.llm.listing.OllamaClient") as client:
            client.return_value.list_models.return_value = MagicMock(error="Cannot reach Ollama")

            with pytest.raises(ListingRefused, match="Cannot reach Ollama"):
                OllamaListing().names(local("ollama", endpoint_url="http://localhost:11434"))


class TestOf:
    """What one listing call reports, for every way it can end."""

    async def test_every_provider_is_reachable_through_the_table(self):
        """A provider with no entry would silently save unvalidated forever."""
        assert set(LISTINGS) == {"openai", "custom", "anthropic", "gemini", "ollama"}

    async def test_the_names_a_provider_serves_come_back(self):
        with patch.object(OpenAIListing, "names", return_value=("gpt-4o",)):
            listing = await ModelListing.of(cloud())

        assert listing.names == ("gpt-4o",)

    async def test_a_local_provider_with_no_endpoint_is_unsupported(self):
        """Nowhere to ask is not the same as a provider that served nothing."""
        listing = await ModelListing.of(local(endpoint_url=""))

        assert (listing.supported, listing.error) == (False, "")

    @pytest.mark.parametrize("status", [401, 403])
    async def test_a_refused_credential_says_so(self, status):
        with patch.object(OpenAIListing, "names", side_effect=refused(status)):
            listing = await ModelListing.of(cloud())

        assert listing.error == "Invalid API key"

    @pytest.mark.parametrize("status", [404, 405])
    async def test_a_server_with_no_index_saves_unvalidated(self, status):
        """Listing is optional in the protocol; this server still completes."""
        with patch.object(OpenAIListing, "names", side_effect=refused(status)):
            listing = await ModelListing.of(local())

        assert (listing.supported, listing.error) == (False, "")

    async def test_another_failing_status_names_the_provider_and_the_code(self):
        with patch.object(OpenAIListing, "names", side_effect=refused(500)):
            listing = await ModelListing.of(cloud())

        assert listing.error == "OpenAI (GPT) refused the request: HTTP 500"

    async def test_a_google_status_is_read_off_its_own_attribute(self):
        """Google's SDK carries `code` where the others carry `status_code`."""
        with patch.object(GeminiListing, "names", side_effect=refused_by_google(401)):
            listing = await ModelListing.of(cloud("gemini"))

        assert listing.error == "Invalid API key"

    async def test_an_unreachable_host_is_an_answer_not_a_crash(self):
        with patch.object(OpenAIListing, "names", side_effect=httpx.ConnectError("no route")):
            listing = await ModelListing.of(cloud())

        assert listing.error == "Cannot connect to OpenAI (GPT)"

    async def test_a_timeout_is_told_apart_from_a_refusal(self):
        """The host resolved and hung; that is a different fix from a bad URL."""
        slow = anthropic.APITimeoutError(request=httpx.Request("GET", "http://x"))

        with patch.object(AnthropicListing, "names", side_effect=slow):
            listing = await ModelListing.of(cloud("anthropic"))

        assert listing.error == "Timed out connecting to Anthropic (Claude)"

    def test_every_client_timeout_type_is_declared(self):
        """`openai` raises an httpx2 timeout, which is not an `httpx` one."""
        assert set(TIMEOUTS) == {
            httpx.TimeoutException,
            openai.APITimeoutError,
            anthropic.APITimeoutError,
        }

    async def test_a_timeout_is_found_through_the_cause_chain(self):
        """Google raises httpx's type; the others wrap it and chain the original."""
        wrapped = genai_errors.APIError(0, {})
        wrapped.__cause__ = httpx.ReadTimeout("slow")

        with patch.object(GeminiListing, "names", side_effect=wrapped):
            listing = await ModelListing.of(cloud("gemini"))

        assert listing.error == "Timed out connecting to Google (Gemini)"

    async def test_an_ollama_refusal_keeps_its_message(self):
        refused = ListingRefused("Connected but no models installed")

        with patch.object(OllamaListing, "names", side_effect=refused):
            listing = await ModelListing.of(local("ollama", endpoint_url="http://localhost:11434"))

        assert listing.error == "Connected but no models installed"


class TestMissing:
    """Which configured models a provider did not list."""

    def test_a_model_that_was_listed_is_not_missing(self):
        listing = ModelListing(names=("gpt-4o", "gpt-4o-mini"))

        assert listing.missing(["gpt-4o"]) == ()

    def test_a_model_that_was_not_listed_is_named(self):
        listing = ModelListing(names=("gpt-4o",))

        assert listing.missing(["gpt-4o", "typo"]) == ("typo",)

    @pytest.mark.parametrize(
        ("served", "wanted"),
        [
            ("llama3:latest", "llama3"),
            ("llama3", "llama3:latest"),
            ("GPT-4o", "gpt-4o"),
            ("gpt-4o", " gpt-4o "),
        ],
    )
    def test_two_spellings_of_one_model_match(self, served, wanted):
        """A server lists `llama3:latest` for what the user typed as `llama3`."""
        assert ModelListing(names=(served,)).missing([wanted]) == ()

    @pytest.mark.parametrize(
        "listing",
        [
            ModelListing(supported=False),
            ModelListing(error="Cannot connect to OpenAI (GPT)"),
            ModelListing(names=()),
        ],
    )
    def test_an_unusable_listing_refuses_nothing(self, listing):
        """A provider that will not enumerate must not block a save."""
        assert listing.missing(["anything"]) == ()


class TestConfiguredModels:
    """What a section will actually ask a provider for."""

    def test_both_roles_are_wanted(self):
        section = cloud(model_analysis="big", model_generation="small")

        assert section.configured_models == ("big", "small")

    def test_one_model_named_twice_is_wanted_once(self):
        section = cloud(model_analysis="same", model_generation="same")

        assert section.configured_models == ("same",)

    def test_smart_generation_wants_only_the_analysis_model(self):
        section = cloud(model_analysis="big", model_generation="small", smart_generation=True)

        assert section.configured_models == ("big",)

    def test_an_unset_model_is_not_wanted(self):
        """An empty name is a section not finished, not a model to look for."""
        assert cloud(model_analysis="big").configured_models == ("big",)
