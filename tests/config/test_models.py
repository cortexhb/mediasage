"""Tests for the pure configuration data models."""

import pytest
from pydantic import ValidationError

from backend.config import (
    ArtConfig,
    BudgetConfig,
    CloudLLMConfig,
    ConfigUpdate,
    LocalLLMConfig,
    MatchingConfig,
    PlexConfig,
    RecommendConfig,
    ResearchConfig,
)


class TestPlexConfig:
    """Tests for Plex section validation."""

    def test_strips_trailing_slash(self):
        """Should strip the trailing slash so joined paths do not double up."""
        assert PlexConfig(url="http://plex:32400/").url == "http://plex:32400"

    def test_rejects_blank_music_library(self):
        """Should reject a blank library name."""
        with pytest.raises(ValidationError):
            PlexConfig(music_library="")

    def test_is_frozen(self):
        """Sections are replaced wholesale, never mutated."""
        assert PlexConfig.model_config["frozen"] is True


class TestLLMConfig:
    """Tests for LLM section validation."""

    def _config(
        self,
        context_window: int = 32768,
        endpoint_url: str = "http://localhost:5000/v1",
    ) -> LocalLLMConfig:
        return LocalLLMConfig(
            provider="custom",
            model_analysis="m",
            model_generation="m",
            endpoint_url=endpoint_url,
            context_window=context_window,
        )

    def test_rejects_context_window_below_minimum(self):
        """Should reject a context window too small for a trimmed prompt."""
        with pytest.raises(ValidationError):
            self._config(context_window=16)

    def test_rejects_context_window_above_maximum(self):
        """Should reject a context window that can only be a misconfiguration."""
        with pytest.raises(ValidationError):
            self._config(context_window=9_000_000)

    def test_strips_trailing_slash_from_urls(self):
        """Should strip trailing slashes from endpoint URLs."""
        assert (
            self._config(endpoint_url="http://host:5000/v1/").endpoint_url == "http://host:5000/v1"
        )

    def test_local_and_cloud_differ_by_class(self):
        """Locality is a fact about the class, not a lookup on the provider name."""
        assert self._config().is_local is True
        assert CloudLLMConfig(provider="openai", context_window=128_000).is_local is False

    def test_context_window_is_the_configured_value(self):
        """The window is whatever was configured, never inferred."""
        assert self._config(context_window=8192).context_window == 8192

    def test_models_are_not_guessed(self):
        """A provider named without models leaves them blank."""
        config = CloudLLMConfig(provider="openai", context_window=128_000)

        assert config.model_analysis == ""
        assert config.model_generation == ""

    def test_local_requires_an_endpoint(self):
        """A local provider is unreachable without one, so it has no default."""
        with pytest.raises(ValidationError):
            LocalLLMConfig.model_validate({"provider": "custom", "context_window": 32768})

    def test_context_window_is_required_of_every_provider(self):
        """No table to fall back on, so an unset window fails rather than guesses."""
        with pytest.raises(ValidationError):
            CloudLLMConfig.model_validate({"provider": "openai"})

    def test_cloud_carries_no_endpoint(self):
        """An endpoint lives only on the local section."""
        cloud = CloudLLMConfig(provider="openai", context_window=128_000)

        assert not hasattr(cloud, "endpoint_url")


class TestConfigUpdate:
    """Tests for the update payload and the field mapping it owns."""

    def test_is_empty_when_nothing_supplied(self):
        """An update with no values should report itself empty."""
        assert ConfigUpdate().is_empty is True

    def test_is_not_empty_when_a_value_is_supplied(self):
        """Any supplied value should make the update non-empty."""
        assert ConfigUpdate(plex_url="http://plex:32400").is_empty is False

    @pytest.mark.parametrize(
        ("field", "key", "value"),
        [
            ("cost_analysis_input", "cost_analysis_input", 0.0),
            ("cost_generation_output", "cost_generation_output", 0.0),
            ("context_window", "context_window", 0),
            ("model_analysis", "model_analysis", ""),
        ],
    )
    def test_a_falsy_value_is_still_a_change(self, field, key, value):
        """Presence is `is not None`: zero is a value, not an omission."""
        update = ConfigUpdate(**{field: value})

        assert update.is_empty is False
        assert update.changes("llm") == {key: value}

    def test_a_price_change_does_not_reconnect(self):
        """A falsy price is a change, but not one that can stop the provider answering."""
        assert ConfigUpdate(cost_analysis_input=0.0).reconnects("llm") is False

    def test_a_supplied_zero_price_survives_a_provider_switch(self):
        """`provider_changes` blanks only what the caller left out."""
        update = ConfigUpdate(llm_provider="openai", cost_analysis_input=0.0)

        assert "cost_analysis_input" not in update.provider_changes
        assert update.changes("llm")["cost_analysis_input"] == 0.0

    def test_plex_changes_are_keyed_for_the_section(self):
        """API field names should map onto PlexConfig field names."""
        update = ConfigUpdate(plex_url="http://plex:32400", plex_token="tok")

        assert update.changes("plex") == {"url": "http://plex:32400", "token": "tok"}

    def test_llm_changes_include_provider(self):
        """The LLM section owns the provider field."""
        update = ConfigUpdate(llm_provider="openai", llm_api_key="sk-test")

        assert update.changes("llm") == {"provider": "openai", "api_key": "sk-test"}

    def test_touches_plex_only_for_plex_fields(self):
        """Should report whether the Plex client needs rebuilding."""
        assert ConfigUpdate(plex_token="tok").touches("plex") is True
        assert ConfigUpdate(llm_api_key="sk-test").touches("plex") is False

    def test_touches_llm_includes_provider(self):
        """A provider change alone should still rebuild the LLM client."""
        assert ConfigUpdate(llm_provider="openai").touches("llm") is True
        assert ConfigUpdate(plex_token="tok").touches("llm") is False

    def test_rejects_unknown_provider(self):
        """Should reject a provider outside the supported set."""
        with pytest.raises(ValidationError):
            ConfigUpdate.model_validate({"llm_provider": "notaprovider"})


class TestPricing:
    """Tests for the per-role token prices."""

    def _cloud(
        self,
        smart_generation: bool = False,
        model_analysis: str = "",
        model_generation: str = "",
    ) -> CloudLLMConfig:
        return CloudLLMConfig(
            provider="anthropic",
            context_window=200_000,
            cost_analysis_input=3.00,
            cost_analysis_output=15.00,
            cost_generation_input=1.00,
            cost_generation_output=5.00,
            smart_generation=smart_generation,
            model_analysis=model_analysis,
            model_generation=model_generation,
        )

    def test_prices_each_role_separately(self):
        """The analysis and generation models rarely cost the same."""
        config = self._cloud()

        assert config.estimate_cost("analysis", 1_000_000, 0) == pytest.approx(3.00)
        assert config.estimate_cost("generation", 1_000_000, 0) == pytest.approx(1.00)

    def test_sums_input_and_output(self):
        """Both directions are billed."""
        cost = self._cloud().estimate_cost("analysis", 1_000_000, 1_000_000)

        assert cost == pytest.approx(18.00)

    def test_local_inference_is_free(self):
        """Locality wins over any price that happens to be configured."""
        config = LocalLLMConfig(
            provider="custom",
            endpoint_url="http://localhost:1234/v1",
            context_window=32768,
            cost_analysis_input=99.0,
        )

        assert config.estimate_cost("analysis", 1_000_000, 1_000_000) == 0.0

    def test_unpriced_when_nothing_declared(self):
        """An undeclared price reads as unpriced, never as a guess."""
        config = CloudLLMConfig(provider="openai", context_window=128_000)

        assert config.is_priced is False
        assert config.estimate_cost("analysis", 1_000_000, 1_000_000) == 0.0

    def test_local_counts_as_priced(self):
        """Zero is the true price locally, so the UI can show it."""
        config = LocalLLMConfig(
            provider="ollama",
            endpoint_url="http://localhost:11434",
            context_window=8192,
        )

        assert config.is_priced is True

    def test_smart_generation_spends_the_analysis_model(self):
        """`smart_generation` swaps the model, and so the price, for generation."""
        config = self._cloud(smart_generation=True, model_analysis="big", model_generation="small")

        assert config.model_for_generation == "big"


class TestBudgetConfig:
    """Tests for the prompt budgeting section."""

    def test_rejects_a_buffer_of_one(self):
        """A full buffer would leave no room for anything."""
        with pytest.raises(ValidationError):
            BudgetConfig(context_buffer_fraction=1.0)

    def test_rejects_zero_tokens_per_track(self):
        """Zero would divide by zero when budgeting."""
        with pytest.raises(ValidationError):
            BudgetConfig.model_validate({"tokens_per_track": 0})


class TestResearchConfig:
    """Tests for the external research section."""

    def test_rejects_a_break_floor_above_the_cap(self):
        """A floor above the cap would trim every review to the cap instead."""
        with pytest.raises(ValidationError):
            ResearchConfig(review_max_chars=1000, review_min_chars=2000)

    def test_accepts_a_floor_equal_to_the_cap(self):
        assert ResearchConfig(review_max_chars=2000, review_min_chars=2000).review_min_chars == 2000

    def test_rejects_a_non_positive_timeout(self):
        with pytest.raises(ValidationError):
            ResearchConfig.model_validate({"request_timeout": 0})

    def test_endpoints_are_overridable_for_a_mirror(self):
        mirror = ResearchConfig(musicbrainz_url="http://mb.lan/ws/2")
        assert mirror.musicbrainz_url == "http://mb.lan/ws/2"

    def test_reviews_can_be_switched_off(self):
        assert ResearchConfig(max_reviews=0).max_reviews == 0


class TestMatchingConfig:
    """Tests for the fuzzy matching floors."""

    @pytest.mark.parametrize(
        "field",
        (
            "track_threshold",
            "album_artist_min",
            "album_combined_min",
            "pitch_artist_min",
            "pitch_album_min",
        ),
    )
    def test_scores_are_bounded_to_a_ratio(self, field):
        """Every floor is a rapidfuzz ratio, so nothing outside 0-100 is valid."""
        with pytest.raises(ValidationError):
            MatchingConfig.model_validate({field: 101})
        with pytest.raises(ValidationError):
            MatchingConfig.model_validate({field: -1})


class TestRecommendConfig:
    """Tests for the shape of one recommendation round."""

    def test_rejects_a_zero_pick_count(self):
        with pytest.raises(ValidationError):
            RecommendConfig.model_validate({"pick_count": 0})

    def test_rejects_a_zero_expiry(self):
        with pytest.raises(ValidationError):
            RecommendConfig.model_validate({"session_expiry": 0})

    def test_history_can_be_switched_off(self):
        assert RecommendConfig(recent_limit=0).recent_limit == 0


class TestArtConfig:
    """Tests for the art proxy section."""

    def test_rejects_a_negative_cache_age(self):
        with pytest.raises(ValidationError):
            ArtConfig.model_validate({"cache_max_age": -1})

    def test_the_allowlist_is_replaceable(self):
        """A deployment mirroring cover art needs its own host allowed."""
        assert ArtConfig(external_domains=["art.lan"]).external_domains == ["art.lan"]


class TestProviderPresentation:
    """What the settings form reads off a configured provider."""

    def cloud(self) -> CloudLLMConfig:
        return CloudLLMConfig(provider="anthropic", api_key="k", context_window=200000)

    def local(self) -> LocalLLMConfig:
        return LocalLLMConfig(
            provider="ollama", endpoint_url="http://nas:11434", context_window=32768
        )

    def test_a_provider_is_labelled_for_the_form(self):
        assert self.cloud().label == "Anthropic (Claude)"
        assert self.local().label == "Ollama (Local)"

    def test_a_local_provider_reports_its_endpoint(self):
        assert self.local().local_endpoint == "http://nas:11434"

    def test_a_hosted_provider_reports_none(self):
        """The form hides the URL field rather than showing a stale one."""
        assert self.cloud().local_endpoint == ""


class TestCredentialsAreSecret:
    """Every credential is a `SecretStr`, so nothing incidental prints it."""

    TOKEN = "plex-tok-do-not-print"
    KEY = "sk-do-not-print"

    def plex(self) -> PlexConfig:
        return PlexConfig(url="http://plex:32400", token=self.TOKEN)

    def llm(self) -> CloudLLMConfig:
        return CloudLLMConfig(provider="anthropic", api_key=self.KEY, context_window=200000)

    def test_a_repr_masks_the_plex_token(self):
        """A traceback frame renders the model, so the repr must not carry it."""
        assert self.TOKEN not in repr(self.plex())

    def test_a_repr_masks_the_api_key(self):
        assert self.KEY not in repr(self.llm())

    def test_a_json_dump_masks_both(self):
        """Anything serialising a section for a log or a response is safe."""
        assert self.TOKEN not in str(self.plex().model_dump(mode="json"))
        assert self.KEY not in str(self.llm().model_dump(mode="json"))

    def test_the_value_is_still_reachable_where_it_is_spent(self):
        assert self.plex().token.get_secret_value() == self.TOKEN
        assert self.llm().api_key.get_secret_value() == self.KEY

    def test_an_unset_credential_is_falsy(self):
        """`is_configured` and the lifespan both test the credential directly."""
        assert not PlexConfig().token
        assert not CloudLLMConfig(provider="anthropic", context_window=200000).is_configured


class TestSecretsReachTheConfigFile:
    """What `ConfigStore.save` writes must be the credential, not the mask."""

    def test_a_plex_token_is_unwrapped_for_persistence(self):
        """Left wrapped, the deployment would restart unconfigured."""
        update = ConfigUpdate(plex_url="http://plex:32400", plex_token="tok")

        assert update.changes("plex")["token"] == "tok"

    def test_an_api_key_is_unwrapped_for_persistence(self):
        update = ConfigUpdate(llm_provider="anthropic", llm_api_key="sk-real")

        assert update.changes("llm")["api_key"] == "sk-real"

    def test_a_blank_credential_is_not_written(self):
        """An empty secret is falsy, so it never reaches the file."""
        assert "token" not in ConfigUpdate(plex_url="http://plex:32400").changes("plex")
