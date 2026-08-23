"""Fixed literals for the LLM package.

Structural facts about providers and their output formats — not deployment
settings. Anything that varies from machine to machine lives on `LLMConfig` or
`BudgetConfig` instead, where the user can change it.
"""

import re
from typing import Final

from backend.config import Provider

# Our provider names mapped to LangChain's. `custom` is OpenAI plus a base_url.
PROVIDER_IDS: Final[dict[Provider, str]] = {
    "anthropic": "anthropic",
    "openai": "openai",
    "gemini": "google_genai",
    "ollama": "ollama",
    "custom": "openai",
}

# OpenAI-compatible endpoints reject an empty key even when they ignore it.
PLACEHOLDER_API_KEY: Final = "not-needed"

# ```json first: a prose fence must never win over a tagged one.
JSON_FENCE: Final = re.compile(r"```json\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)
ANY_FENCE: Final = re.compile(r"```(?:\w+)?\s*\n?(.*?)```", re.DOTALL)

# Typographic quotes models emit inside otherwise valid JSON.
SMART_QUOTES: Final = str.maketrans({"\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'"})

# Longest snippet echoed back in a parse error, enough to identify it.
ERROR_PREVIEW_CHARS: Final = 200

# Ollama reports a native window under keys like "qwen3.context_length".
CONTEXT_LENGTH_SUFFIX: Final = ".context_length"

# An explicit num_ctx in the Modelfile overrides the architecture's native size.
NUM_CTX_PARAMETER: Final = "num_ctx"
