"""One conversation with a provider, addressed by role.

`LLMClient` is the only thing in the codebase that sends a prompt. It spends
either the analysis model or the generation model -- which differ only in which
configured name, and so which price, they carry -- and returns the completion
with the token counts the provider reported.

Which model each role resolves to, and how it is built, is `chat.ChatModels`.
Reading JSON back out of a completion is `LLMResponse.parsed`. Retries and
timeouts are the integration's own, configured from `LLMConfig`; nothing here
hand-rolls a retry loop.
"""

import logging
from typing import Self

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict

from backend.config import LLMSection, Provider, Role
from backend.llm.chat import ChatModels
from backend.llm.errors import LLMError, LLMNotConfigured
from backend.llm.models import LLMResponse

logger = logging.getLogger(__name__)


class LLMClient(BaseModel):
    """One configured provider, addressed by role rather than by model name."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    models: ChatModels

    @classmethod
    def of(cls, config: LLMSection) -> Self:
        """The client for one configuration."""
        return cls(models=ChatModels(config=config))

    @property
    def config(self) -> LLMSection:
        """The configuration this client was built from."""
        return self.models.config

    @property
    def provider(self) -> Provider:
        """Which provider is being spent, for logs and error messages."""
        return self.models.config.provider

    def complete(self, prompt: str, system: str, role: Role) -> LLMResponse:
        """Run one completion and return it with the provider's token counts.

        Raises:
            LLMError: If the provider returns no usable content
        """
        name = self.models.name_for(role)
        logger.info(
            "Calling %s (%s) for %s with %d char prompt",
            self.provider,
            name,
            role,
            len(prompt),
        )

        message = self.models.for_role(role).invoke(
            [SystemMessage(content=system), HumanMessage(content=prompt)]
        )
        response = LLMResponse.from_message(message, model=name, role=role)

        if not response.content.strip():
            raise LLMError(
                f"{self.provider} returned an empty response. The context window "
                f"({self.config.context_window:,} tokens) may be too small for "
                "this request; try sending fewer tracks."
            )

        logger.debug(
            "%s returned %d chars, %d in / %d out tokens",
            self.provider,
            len(response.content),
            response.input_tokens,
            response.output_tokens,
        )
        return response

    def analyze(self, prompt: str, system: str) -> LLMResponse:
        """Spend the analysis model, for understanding tasks."""
        return self.complete(prompt, system, "analysis")

    def generate(self, prompt: str, system: str) -> LLMResponse:
        """Spend the generation model, for track and album selection."""
        return self.complete(prompt, system, "generation")


class LLMClientStore:
    """Holds the client the application talks through.

    Built from configuration at startup and rebuilt whenever settings change,
    so a stale client can never outlive the config that produced it.

    A plain class, not a model: its methods are depended on directly by the
    routes, and a bound method of an unfrozen pydantic model is unhashable.
    """

    def __init__(self) -> None:
        self.client: LLMClient | None = None

    def get(self) -> LLMClient | None:
        """The current client, or None before one is configured."""
        return self.client

    def require(self) -> LLMClient:
        """The current client, failing loudly rather than returning None.

        Raises:
            LLMNotConfigured: If no provider has been configured yet
        """
        if self.client is None:
            raise LLMNotConfigured("LLM client not configured. Set a provider in Settings.")
        return self.client


# The single instance the application talks through. `client` is assigned
# wherever the LLM settings change: at boot, and after a save.
client_store = LLMClientStore()
