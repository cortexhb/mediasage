"""Tests for the LLM data models."""

import pytest
from langchain_core.messages import AIMessage

from backend.config import BudgetConfig, CloudLLMConfig
from backend.llm import LLMResponse, TokenBudget


class TestLLMResponse:
    """Tests for the provider-neutral completion result."""

    def test_reads_usage_metadata(self):
        """Token counts come from the provider, never from an estimate."""
        message = AIMessage(
            content="hello",
            usage_metadata={"input_tokens": 12, "output_tokens": 5, "total_tokens": 17},
        )

        response = LLMResponse.from_message(message, model="m", role="analysis")

        assert response.input_tokens == 12
        assert response.output_tokens == 5
        assert response.total_tokens == 17

    def test_survives_a_provider_that_reports_no_usage(self):
        """A missing usage block must not break the call."""
        response = LLMResponse.from_message(AIMessage(content="hi"), model="m", role="generation")

        assert response.input_tokens == 0
        assert response.output_tokens == 0

    def test_flattens_block_content(self):
        """Providers that stream reasoning return content as a block list."""
        message = AIMessage(
            content=[
                {"type": "thinking", "thinking": "hmm"},
                {"type": "text", "text": "the answer"},
            ]
        )

        response = LLMResponse.from_message(message, model="m", role="analysis")

        assert response.content == "the answer"

    def test_costs_at_the_price_for_its_role(self, cloud_config: CloudLLMConfig):
        """A generation response is billed at generation rates."""
        response = LLMResponse(
            content="x",
            input_tokens=1_000_000,
            output_tokens=0,
            model="m",
            role="generation",
        )

        assert response.cost(cloud_config) == pytest.approx(1.00)


class TestTokenBudget:
    """Tests for how much of the library fits in one prompt."""

    def _budget(self, context_window: int, **overrides) -> TokenBudget:
        return TokenBudget(context_window=context_window, budget=BudgetConfig(**overrides))

    def test_subtracts_buffer_and_reserve(self):
        """Available space is the window less the buffer and the reserve."""
        budget = self._budget(100_000)

        assert budget.available_tokens == 89_000

    def test_tracks_divide_by_the_per_track_figure(self):
        """Track capacity is available tokens over the per-track cost."""
        assert self._budget(100_000).max_tracks == 89_000 // 40

    def test_albums_divide_by_the_per_album_figure(self):
        """Albums are cheaper per line than tracks, so more of them fit."""
        assert self._budget(100_000).max_albums == 89_000 // 25

    def test_a_window_too_small_yields_nothing(self):
        """No floor: overflowing a tiny window silently is worse than sending zero."""
        budget = self._budget(512)

        assert budget.available_tokens == 0
        assert budget.max_tracks == 0
        assert budget.max_albums == 0

    def test_honours_a_tuned_per_track_figure(self):
        """The per-item figures are the user's to change."""
        assert self._budget(100_000, tokens_per_track=80).max_tracks == 89_000 // 80

    def test_of_reads_the_window_from_the_llm_section(self):
        """The window belongs to the LLM config, the rates to the budget config."""
        llm = CloudLLMConfig(provider="openai", context_window=128_000)

        assert TokenBudget.of(llm, BudgetConfig()).context_window == 128_000
