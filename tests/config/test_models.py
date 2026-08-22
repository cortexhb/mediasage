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
        config = PlexConfig(url="http://plex:32400")

        with pytest.raises(ValidationError):
            config.url = "http://other:32400"


class TestLLMConfig:
    """Tests for LLM section validation."""

    def _config(self, **overrides):
        values = {
            "provider": "custom",
            "model_analysis": "m",
            "model_generation": "m",
            "endpoint_url": "http://localhost:5000/v1",
            "context_window": 32768,
        }
        return LocalLLMConfig(**(values | overrides))

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
        assert self._config(endpoint_url="http://host:5000/v1/").endpoint_url == "http://host:5000/v1"

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
            LocalLLMConfig(provider="custom", context_window=32768)

    def test_context_window_is_required_of_every_provider(self):
        """No table to fall back on, so an unset window fails rather than guesses."""
        with pytest.raises(ValidationError):
            CloudLLMConfig(provider="openai")

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
            ConfigUpdate(llm_provider="notaprovider")


class TestPricing:
    """Tests for the per-role token prices."""

    def _cloud(self, **overrides) -> CloudLLMConfig:
        values = {
            "provider": "anthropic",
            "context_window": 200_000,
            "cost_analysis_input": 3.00,
            "cost_analysis_output": 15.00,
            "cost_generation_input": 1.00,
            "cost_generation_output": 5.00,
        }
        return CloudLLMConfig(**(values | overrides))

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
            BudgetConfig(tokens_per_track=0)


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
            ResearchConfig(request_timeout=0)

    def test_endpoints_are_overridable_for_a_mirror(self):
        mirror = ResearchConfig(musicbrainz_url="http://mb.lan/ws/2")
        assert mirror.musicbrainz_url == "http://mb.lan/ws/2"

    def test_reviews_can_be_switched_off(self):
        assert ResearchConfig(max_reviews=0).max_reviews == 0


class TestMatchingConfig:
    """Tests for the fuzzy matching floors."""

    @pytest.mark.parametrize("field", (
        "track_threshold", "album_artist_min", "album_combined_min",
        "pitch_artist_min", "pitch_album_min",
    ))
    def test_scores_are_bounded_to_a_ratio(self, field):
        """Every floor is a rapidfuzz ratio, so nothing outside 0-100 is valid."""
        with pytest.raises(ValidationError):
            MatchingConfig(**{field: 101})
        with pytest.raises(ValidationError):
            MatchingConfig(**{field: -1})


class TestRecommendConfig:
    """Tests for the shape of one recommendation round."""

    def test_rejects_a_zero_pick_count(self):
        with pytest.raises(ValidationError):
            RecommendConfig(pick_count=0)

    def test_rejects_a_zero_expiry(self):
        with pytest.raises(ValidationError):
            RecommendConfig(session_expiry=0)

    def test_history_can_be_switched_off(self):
        assert RecommendConfig(recent_limit=0).recent_limit == 0


class TestArtConfig:
    """Tests for the art proxy section."""

    def test_rejects_a_negative_cache_age(self):
        with pytest.raises(ValidationError):
            ArtConfig(cache_max_age=-1)

    def test_the_allowlist_is_replaceable(self):
        """A deployment mirroring cover art needs its own host allowed."""
        assert ArtConfig(external_domains=["art.lan"]).external_domains == ["art.lan"]
