"""LLM access: completions, prompt budgeting, JSON recovery, Ollama admin.

`models` holds the data, `chat` turns configuration into chat models, `client`
owns the single conversation with a provider, `json_parse` recovers structure
from prose, `errors` holds the failure both halves raise, `ollama` covers the
one admin API LangChain does not, and `constants` holds the fixed literals.
`client_store` holds the process-level client.
"""

from backend.llm.chat import ChatModels
from backend.llm.client import LLMClient, LLMClientStore, client_store
from backend.llm.constants import PROVIDER_IDS
from backend.llm.errors import LLMError, LLMNotConfigured
from backend.llm.json_parse import JSONParseError, ModelReply
from backend.llm.models import (
    LLMResponse,
    OllamaModel,
    OllamaModelInfo,
    OllamaModelsResponse,
    OllamaStatus,
    TokenBudget,
)
from backend.llm.ollama import OllamaClient

__all__ = [
    "PROVIDER_IDS",
    "ChatModels",
    "JSONParseError",
    "LLMClient",
    "LLMClientStore",
    "LLMError",
    "LLMNotConfigured",
    "LLMResponse",
    "ModelReply",
    "OllamaClient",
    "OllamaModel",
    "OllamaModelInfo",
    "OllamaModelsResponse",
    "OllamaStatus",
    "TokenBudget",
    "client_store",
]
