"""Data models for LLM calls, prompt budgeting, and Ollama administration.

`LLMResponse` is the provider-neutral result every completion returns, built
from LangChain's `AIMessage` so token counts are the ones the provider actually
reported rather than an estimate. `TokenBudget` answers how much of the library
fits in one prompt. The `Ollama*` models describe Ollama's admin API and are
used only by `backend.llm.ollama`.
"""

from typing import Any

from pydantic import BaseModel, Field

from backend.config import BudgetConfig, LLMConfig, Role


class TokenBudget(BaseModel):
    """The prompt space available under one LLM configuration.

    Counts are pre-flight estimates from the per-item figures in `BudgetConfig`;
    authoritative counts come back on the response. A window too small to hold
    anything yields zero rather than a floor, so the caller fails on a
    misconfiguration instead of overflowing the model.
    """

    context_window: int
    budget: BudgetConfig

    @classmethod
    def of(cls, llm: LLMConfig, budget: BudgetConfig) -> TokenBudget:
        return cls(context_window=llm.context_window, budget=budget)

    @property
    def available_tokens(self) -> int:
        """Tokens left for library items, never negative."""
        usable = int(self.context_window * (1 - self.budget.context_buffer_fraction))
        return max(0, usable - self.budget.reserved_prompt_tokens)

    @property
    def max_tracks(self) -> int:
        return self.available_tokens // self.budget.tokens_per_track

    @property
    def max_albums(self) -> int:
        return self.available_tokens // self.budget.tokens_per_album


class LLMResponse(BaseModel):
    """One completion, with the token counts the provider reported."""

    content: str
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    model: str
    role: Role

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def cost(self, config: LLMConfig) -> float:
        """Cost in USD at the prices the user declared for this call's role."""
        return config.estimate_cost(self.role, self.input_tokens, self.output_tokens)

    @classmethod
    def from_message(cls, message: Any, model: str, role: Role) -> LLMResponse:
        """Build from a LangChain `AIMessage`.

        `usage_metadata` is absent on providers that do not report usage, and
        `content` arrives as a block list on providers that stream reasoning.
        """
        usage = getattr(message, "usage_metadata", None) or {}
        return cls(
            content=cls.text_of(message),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            model=model,
            role=role,
        )

    @staticmethod
    def text_of(message: Any) -> str:
        """Flatten message content to text, whether it is a string or blocks."""
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "".join(parts)


class OllamaModel(BaseModel):
    """A model available in Ollama."""

    name: str
    size: int = 0
    modified_at: str = ""


class OllamaModelInfo(BaseModel):
    """Detailed info about an Ollama model."""

    name: str
    context_window: int | None = None
    parameter_size: str | None = None


class OllamaModelsResponse(BaseModel):
    """Response from listing Ollama models."""

    models: list[OllamaModel] = []
    error: str | None = None


class OllamaStatus(BaseModel):
    """Connection status for Ollama."""

    connected: bool
    model_count: int = 0
    error: str | None = None
