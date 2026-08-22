"""Provider-neutral chat completions, on top of LangChain.

`LLMClient` is the only thing in the codebase that talks to a model. It builds
one LangChain chat model per configuration and exposes `analyze` and `generate`,
which differ only in which configured model — and so which price — they spend.

LangChain's `init_chat_model` handles every provider we support behind one
signature, so there is no per-provider branch here beyond the name mapping in
`PROVIDER_IDS`. `custom` is OpenAI-compatible and is reached by pointing the
OpenAI integration at the configured `base_url`.

Retries and timeouts are the integration's own, configured from `LLMConfig`;
nothing here hand-rolls a retry loop.
"""

import logging
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict

from backend.config import LLMSection, LocalLLMConfig, Provider, Role
from backend.llm.constants import PLACEHOLDER_API_KEY, PROVIDER_IDS
from backend.llm.json_parse import parse_json
from backend.llm.models import LLMResponse

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised when a provider returns nothing usable."""

# TODO half of this is model, half is business logic
class LLMClient:
    """One configured provider, addressed by role rather than by model name."""

    def __init__(self, config: LLMSection) -> None:
        self.config = config
        self.provider: Provider = config.provider
        self._models: dict[Role, BaseChatModel] = {}

    def model_name(self, role: Role) -> str:
        """The configured model for `role`, honouring `smart_generation`."""
        if role == "analysis":
            return self.config.model_analysis
        return self.config.model_for_generation

    def build_kwargs(self) -> dict[str, Any]:
        """Arguments shared by every provider integration.

        Every supported integration accepts this set; a local endpoint adds
        `base_url` and needs no real key.
        """
        kwargs: dict[str, Any] = {
            "timeout": self.config.request_timeout,
            "max_tokens": self.config.max_output_tokens,
            "max_retries": self.config.max_retries,
        }

        if isinstance(self.config, LocalLLMConfig):
            kwargs["base_url"] = self.config.endpoint_url
            kwargs["api_key"] = self.config.api_key or PLACEHOLDER_API_KEY
        else:
            kwargs["api_key"] = self.config.api_key

        return kwargs

    def model_for(self, role: Role) -> BaseChatModel:
        """The chat model for `role`, built once and reused."""
        if role not in self._models:
            name = self.model_name(role)
            if not name:
                raise LLMError(
                    f"No {role} model configured. Set MEDIASAGE_LLM__MODEL_"
                    f"{role.upper()} or choose one in Settings."
                )
            self._models[role] = init_chat_model(
                model=name,
                model_provider=PROVIDER_IDS[self.provider],
                **self.build_kwargs(),
            )
        return self._models[role]

    def complete(self, prompt: str, system: str, role: Role) -> LLMResponse:
        """Run one completion and return it with the provider's token counts.

        Raises:
            LLMError: If the provider returns no usable content
        """
        name = self.model_name(role)
        logger.info(
            "Calling %s (%s) for %s with %d char prompt",
            self.provider, name, role, len(prompt),
        )

        message = self.model_for(role).invoke(
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
            self.provider, len(response.content),
            response.input_tokens, response.output_tokens,
        )
        return response

    def analyze(self, prompt: str, system: str) -> LLMResponse:
        """Spend the analysis model, for understanding tasks."""
        return self.complete(prompt, system, "analysis")

    def generate(self, prompt: str, system: str) -> LLMResponse:
        """Spend the generation model, for track and album selection."""
        return self.complete(prompt, system, "generation")

    @staticmethod
    def parse_json_response(response: LLMResponse) -> Any:
        """Decode a response's content as JSON, repairing what models get wrong."""
        return parse_json(response.content)


class LLMClientStore(BaseModel):
    """Holds the client the application talks through.

    Built from configuration at startup and rebuilt whenever settings change,
    so a stale client can never outlive the config that produced it.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)

    client: LLMClient | None = None

    def get(self) -> LLMClient | None:
        """The current client, or None before one is configured."""
        return self.client

    def require(self) -> LLMClient:
        """The current client, failing loudly rather than returning None.

        Raises:
            LLMError: If no provider has been configured yet
        """
        if self.client is None:
            raise LLMError("LLM client not configured. Set a provider in Settings.")
        return self.client

    def init(self, config: LLMSection) -> LLMClient:
        """Replace the client with one built from `config`."""
        self.client = LLMClient(config)
        return self.client


# The single instance the application talks through.
client_store = LLMClientStore()
