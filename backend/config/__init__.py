"""Configuration loading, validation, and persistence.

`models` holds the pure section models, `settings` owns the loading concern,
and `store` owns the process-level instance plus UI-saved settings.
"""

from backend.config import settings
from backend.config.models import (
    LLM_SECTION_ADAPTER,
    ArtConfig,
    BudgetConfig,
    CloudLLMConfig,
    ConfigSection,
    ConfigUpdate,
    DefaultsConfig,
    LibraryConfig,
    LLMConfig,
    LLMSection,
    LocalLLMConfig,
    MatchingConfig,
    PlexConfig,
    Provider,
    RecommendConfig,
    ResearchConfig,
    Role,
)
from backend.config.settings import (
    BASE_CONFIG_PATH,
    USER_CONFIG_PATH,
    MediasageConfig,
    load_config,
)
from backend.config.store import ConfigSaveError, ConfigStore, config_store

__all__ = [
    "BASE_CONFIG_PATH",
    "LLM_SECTION_ADAPTER",
    "USER_CONFIG_PATH",
    "ArtConfig",
    "BudgetConfig",
    "CloudLLMConfig",
    "ConfigSaveError",
    "ConfigSection",
    "ConfigStore",
    "ConfigUpdate",
    "DefaultsConfig",
    "LLMConfig",
    "LLMSection",
    "LibraryConfig",
    "LocalLLMConfig",
    "MatchingConfig",
    "MediasageConfig",
    "PlexConfig",
    "Provider",
    "RecommendConfig",
    "ResearchConfig",
    "Role",
    "config_store",
    "load_config",
    "settings",
]
