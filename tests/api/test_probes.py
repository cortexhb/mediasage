"""Tests for proving a candidate configuration before it is saved.

A probe never raises: every way a dependency can refuse is an answer a form
has to show.
"""

from unittest.mock import AsyncMock, patch

from backend.api.probes import LLMProbe, Probe
from backend.config import ConfigUpdate
from backend.llm import ModelListing
from tests.api.conftest import mediasage_config


def listed(**fields) -> AsyncMock:
    """`ModelListing.of` answering with one listing, whatever it was asked."""
    return AsyncMock(return_value=ModelListing(**fields))


class TestLLMProbe:
    """A probe lists models. It must never spend a completion to do it."""

    async def test_a_provider_serving_both_models_is_ok(self):
        section = mediasage_config(model_analysis="big", model_generation="small").llm

        with patch("backend.api.probes.ModelListing.of", listed(names=("big", "small"))):
            probe = await LLMProbe.of(section)

        assert probe.ok is True

    async def test_no_completion_is_spent(self):
        """Configuring inference must not bill the user for inference."""
        with (
            patch("backend.api.probes.ModelListing.of", listed(names=("gpt-4o",))),
            patch("backend.llm.client.LLMClient.complete") as complete,
        ):
            await LLMProbe.of(mediasage_config(model_analysis="gpt-4o").llm)

        complete.assert_not_called()

    async def test_a_model_the_provider_does_not_serve_is_named(self):
        section = mediasage_config(model_analysis="typo", model_generation="typo").llm

        with patch("backend.api.probes.ModelListing.of", listed(names=("gpt-4o",))):
            probe = await LLMProbe.of(section)

        assert probe.error == "Anthropic (Claude) does not serve typo"

    async def test_a_listing_the_provider_will_not_give_refuses_nothing(self):
        """No listing endpoint means saving unvalidated, not saving refused."""
        section = mediasage_config(model_analysis="anything").llm

        with patch("backend.api.probes.ModelListing.of", listed(supported=False)):
            probe = await LLMProbe.of(section)

        assert probe.ok is True

    async def test_a_listing_error_becomes_the_probe_error(self):
        with patch("backend.api.probes.ModelListing.of", listed(error="Invalid API key")):
            probe = await LLMProbe.of(mediasage_config().llm)

        assert (probe.ok, probe.error) == (False, "Invalid API key")

    async def test_an_unreachable_host_names_the_provider(self):
        section = mediasage_config(llm_provider="ollama").llm

        with patch("backend.api.probes.ModelListing.of", listed(error="Could not resolve host")):
            probe = await LLMProbe.of(section)

        assert probe.error == "Cannot connect to Ollama (Local)"


class TestRejected:
    """Only what a change could break is probed."""

    async def test_a_price_edit_touches_nothing(self):
        with patch("backend.api.probes.ModelListing.of", listed()) as listing:
            refusal = await Probe.rejection(
                ConfigUpdate(cost_analysis_input=3.0), mediasage_config()
            )

        assert refusal == ""
        listing.assert_not_called()

    async def test_a_music_library_edit_spends_nothing(self):
        """Plex resolves the library name later, and is not probed here at all."""
        with patch("backend.api.probes.ModelListing.of", listed()) as listing:
            refusal = await Probe.rejection(ConfigUpdate(music_library="Other"), mediasage_config())

        assert refusal == ""
        listing.assert_not_called()

    async def test_a_provider_that_will_not_answer_is_named(self):
        with patch("backend.api.probes.ModelListing.of", listed(error="nope")):
            refusal = await Probe.rejection(ConfigUpdate(llm_provider="openai"), mediasage_config())

        assert refusal == "Anthropic (Claude): nope"

    async def test_a_change_that_breaks_nothing_is_not_refused(self):
        with patch("backend.api.probes.ModelListing.of", listed(supported=False)):
            refusal = await Probe.rejection(ConfigUpdate(llm_provider="openai"), mediasage_config())

        assert refusal == ""
