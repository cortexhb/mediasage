"""Tests for proving a candidate configuration before it is saved.

A probe never raises: every way a dependency can refuse is an answer a form
has to show.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from backend.api.probes import LLMProbe, PlexProbe, Probe
from backend.config import ConfigUpdate, PlexConfig
from backend.llm import ModelListing
from tests.api.conftest import mediasage_config

CANDIDATE = PlexConfig(url="http://plex:32400", token="tok", music_library="Music")


def plex_answering(**attributes) -> MagicMock:
    """A Plex client that connects and reports what the wizard shows next."""
    client = MagicMock(**attributes)
    client.connection.server_name = "My Plex Server"
    client.connection.is_connected.return_value = True
    client.connection.music_libraries.return_value = ["Music", "Audiobooks"]
    return client


class TestPlexProbe:
    async def test_a_connected_server_is_ok(self):
        with patch("backend.api.probes.PlexClient.of", return_value=plex_answering()):
            probe = await PlexProbe.of(CANDIDATE)

        assert probe.ok is True

    async def test_what_the_wizard_shows_next_is_read_off_the_probe(self):
        with patch("backend.api.probes.PlexClient.of", return_value=plex_answering()):
            probe = await PlexProbe.of(CANDIDATE)

        assert probe.server_name == "My Plex Server"
        assert probe.music_libraries == ["Music", "Audiobooks"]

    async def test_a_refused_connection_carries_the_reason(self):
        refused = MagicMock()
        refused.connection.is_connected.return_value = False
        refused.connection.error = "Invalid Plex token - unauthorized"

        with patch("backend.api.probes.PlexClient.of", return_value=refused):
            probe = await PlexProbe.of(CANDIDATE)

        assert (probe.ok, probe.error) == (False, "Invalid Plex token - unauthorized")

    async def test_a_client_that_will_not_build_is_an_answer_not_a_crash(self):
        with patch("backend.api.probes.PlexClient.of", side_effect=RuntimeError("no route")):
            probe = await PlexProbe.of(CANDIDATE)

        assert (probe.ok, probe.error) == (False, "no route")

    async def test_a_connection_with_no_reason_still_says_something(self):
        """A form cannot show an empty error."""
        silent = MagicMock()
        silent.connection.is_connected.return_value = False
        silent.connection.error = None

        with patch("backend.api.probes.PlexClient.of", return_value=silent):
            probe = await PlexProbe.of(CANDIDATE)

        assert probe.error == "Connection failed"


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
        with (
            patch("backend.api.probes.PlexClient") as plex,
            patch("backend.api.probes.ModelListing.of", listed()) as listing,
        ):
            refusal = await Probe.rejection(
                ConfigUpdate(cost_analysis_input=3.0), mediasage_config()
            )

        assert refusal == ""
        plex.of.assert_not_called()
        listing.assert_not_called()

    async def test_a_music_library_edit_spends_nothing(self):
        """Plex resolves the library name later; it cannot stop the server answering."""
        with patch("backend.api.probes.PlexClient") as plex:
            refusal = await Probe.rejection(ConfigUpdate(music_library="Other"), mediasage_config())

        assert refusal == ""
        plex.of.assert_not_called()

    async def test_a_plex_that_will_not_answer_is_named(self):
        refused = MagicMock()
        refused.connection.is_connected.return_value = False
        refused.connection.error = "unauthorized"

        with patch("backend.api.probes.PlexClient.of", return_value=refused):
            refusal = await Probe.rejection(
                ConfigUpdate(plex_url="http://new:32400"), mediasage_config()
            )

        assert refusal == "Plex: unauthorized"

    async def test_a_provider_that_will_not_answer_is_named(self):
        with patch("backend.api.probes.ModelListing.of", listed(error="nope")):
            refusal = await Probe.rejection(ConfigUpdate(llm_provider="openai"), mediasage_config())

        assert refusal == "Anthropic (Claude): nope"

    async def test_a_change_that_breaks_nothing_is_not_refused(self):
        with (
            patch("backend.api.probes.PlexClient.of", return_value=plex_answering()),
            patch("backend.api.probes.ModelListing.of", listed(supported=False)),
        ):
            refusal = await Probe.rejection(
                ConfigUpdate(plex_url="http://new:32400", llm_provider="openai"),
                mediasage_config(),
            )

        assert refusal == ""
