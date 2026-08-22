"""LLM access: completions, prompt budgeting, JSON recovery, Ollama admin.

`models` holds the data, `client` owns the single conversation with a provider,
`json_parse` recovers structure from prose, `ollama` covers the one admin API
LangChain does not, and `constants` holds the fixed literals. `client_store`
holds the process-level client.
"""

from backend.llm.client import LLMClient, LLMClientStore, LLMError, client_store
from backend.llm.constants import PROVIDER_IDS
from backend.llm.json_parse import JSONParseError, extract_json_bounds, parse_json
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
    "JSONParseError",
    "LLMClient",
    "LLMClientStore",
    "LLMError",
    "LLMResponse",
    "OllamaClient",
    "OllamaModel",
    "OllamaModelInfo",
    "OllamaModelsResponse",
    "OllamaStatus",
    "TokenBudget",
    "client_store",
    "extract_json_bounds",
    "parse_json",
]
