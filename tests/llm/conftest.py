"""Fixtures for the LLM package tests."""

import pytest

from backend.config import CloudLLMConfig, LocalLLMConfig


@pytest.fixture
def cloud_config() -> CloudLLMConfig:
    """A hosted provider with both models and prices set."""
    return CloudLLMConfig(
        provider="anthropic",
        api_key="sk-test",
        model_analysis="claude-sonnet-4-5",
        model_generation="claude-haiku-4-5",
        context_window=200_000,
        cost_analysis_input=3.00,
        cost_analysis_output=15.00,
        cost_generation_input=1.00,
        cost_generation_output=5.00,
    )


@pytest.fixture
def local_config() -> LocalLLMConfig:
    """An OpenAI-compatible endpoint on the user's own hardware."""
    return LocalLLMConfig(
        provider="custom",
        endpoint_url="http://localhost:1234/v1",
        model_analysis="local-model",
        model_generation="local-model",
        context_window=32768,
    )
