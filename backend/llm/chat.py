"""Configuration into chat models, one per role.

Everything provider-shaped lives here: which model answers to which role, the
arguments every integration takes, and the cache holding one built model per
role. `LLMClient` above it knows only about roles.

LangChain's `init_chat_model` handles every provider we support behind one
signature, so there is no per-provider branch beyond the name mapping in
`PROVIDER_IDS`. `custom` is OpenAI-compatible and is reached by pointing the
OpenAI integration at the configured `base_url`.
"""

from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ConfigDict, PrivateAttr

from backend.config import LLMSection, LocalLLMConfig, Role
from backend.llm.constants import PLACEHOLDER_API_KEY, PROVIDER_IDS
from backend.llm.errors import LLMError


class ChatModels(BaseModel):
    """The chat models one configuration produces, built on first use."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    config: LLMSection

    # Built models are cached per role: constructing one opens a client, and a
    # generation spends the same role several times over.
    _built: dict[Role, BaseChatModel] = PrivateAttr(default_factory=dict)

    def name_for(self, role: Role) -> str:
        """The configured model for `role`, honouring `smart_generation`."""
        if role == "analysis":
            return self.config.model_analysis
        return self.config.model_for_generation

    def sampling(self) -> dict[str, Any]:
        """The sampling knobs the user set, in the shape each one is sent.

        `temperature` and `top_p` are constructor arguments of every
        integration. The rest are not: they reach an OpenAI-compatible server
        through `model_kwargs`, which the integration puts in the request body
        verbatim. Unset means absent, so no provider is sent a knob it would
        reject.
        """
        named = {"temperature": self.config.temperature, "top_p": self.config.top_p}
        extra = {
            "top_k": self.config.top_k,
            "min_p": self.config.min_p,
            "presence_penalty": self.config.presence_penalty,
            "repetition_penalty": self.config.repetition_penalty,
        }

        chosen: dict[str, Any] = {key: value for key, value in named.items() if value is not None}
        body = {key: value for key, value in extra.items() if value is not None}
        if body:
            chosen["model_kwargs"] = body

        return chosen

    def kwargs(self) -> dict[str, Any]:
        """Arguments shared by every provider integration.

        Every supported integration accepts this set; a local endpoint adds
        `base_url` and needs no real key.
        """
        shared: dict[str, Any] = {
            "timeout": self.config.request_timeout,
            "max_tokens": self.config.max_output_tokens,
            "max_retries": self.config.max_retries,
            **self.sampling(),
        }

        key = self.config.api_key.get_secret_value()
        if isinstance(self.config, LocalLLMConfig):
            shared["base_url"] = self.config.endpoint_url
            shared["api_key"] = key or PLACEHOLDER_API_KEY
        else:
            shared["api_key"] = key

        return shared

    def for_role(self, role: Role) -> BaseChatModel:
        """The chat model for `role`, built once and reused.

        Raises:
            LLMError: If no model is configured for that role
        """
        if role not in self._built:
            name = self.name_for(role)
            if not name:
                raise LLMError(
                    f"No {role} model configured. Set MEDIASAGE_LLM__MODEL_"
                    f"{role.upper()} or choose one in Settings."
                )
            built = init_chat_model(
                model=name,
                model_provider=PROVIDER_IDS[self.config.provider],
                **self.kwargs(),
            )
            # `init_chat_model` widens to `_ConfigurableModel` when no model is
            # named; one always is here, so anything else is a version change.
            if not isinstance(built, BaseChatModel):
                raise LLMError(f"LangChain built no chat model for {name}: {type(built).__name__}")
            self._built[role] = built
        return self._built[role]
