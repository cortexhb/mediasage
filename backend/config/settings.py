"""Top-level configuration model and the sources it loads from.

`MediasageConfig` owns the loading concern. YAML is the ground source; every
setting is also reachable from the environment under one prefix, so nothing
needs a per-field name table.

Precedence, highest first:

1. Values passed to the constructor
2. `MEDIASAGE_*` environment variables
3. `.env`
4. `LANGFUSE_*` variables, and `.env.langfuse` — the tracing section only
5. `data/config.user.yaml` — settings saved from the UI
6. `config.yaml` — the deployment's base file
7. Field defaults

Section fields nest with a double underscore: `MEDIASAGE_LLM__ENDPOINT_URL`,
`MEDIASAGE_DEFAULTS__TRACK_COUNT`.

Plex identity is the exception: it comes from a browser sign-in and no
environment variable can supply it. `Identityless` drops those keys, because
pydantic-settings has no per-field opt-out. See `docs/plex_login.md`.
"""

import os
from pathlib import Path
from typing import Any, Final

from dotenv import dotenv_values
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from backend.config.models import (
    ArtConfig,
    BudgetConfig,
    DefaultsConfig,
    LangfuseConfig,
    LibraryConfig,
    LLMSection,
    MatchingConfig,
    PlexConfig,
    RecommendConfig,
    ResearchConfig,
)

# Base file shipped with the deployment.
BASE_CONFIG_PATH = Path("config.yaml")

# UI-saved settings; in the data volume so they survive container restarts.
USER_CONFIG_PATH = Path("data/config.user.yaml")

# Plex identity keys, ignored wherever the environment offers them.
PLEX_IDENTITY: Final[frozenset[str]] = frozenset(
    {"url", "token", "account_token", "server_id", "client_id", "server_name"}
)

# Separate from `.env` so tracing keys mount on their own.
LANGFUSE_ENV_PATH = Path(".env.langfuse")

# Langfuse's documented variable names, onto the fields they set.
LANGFUSE_ENV: Final[dict[str, str]] = {
    "LANGFUSE_BASE_URL": "base_url",
    "LANGFUSE_PUBLIC_KEY": "public_key",
    "LANGFUSE_SECRET_KEY": "secret_key",
    "LANGFUSE_TRACING_ENVIRONMENT": "environment",
}


class Identityless(PydanticBaseSettingsSource):
    """Another source, with the Plex identity keys removed.

    Wraps rather than replaces: the environment and `.env` sources each know
    how to parse their own nesting, and only their result needs filtering.
    """

    def __init__(self, source: PydanticBaseSettingsSource) -> None:
        super().__init__(source.settings_cls)
        self.source = source

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        """Never called: `__call__` is overridden and does not consult it."""
        raise NotImplementedError

    def __call__(self) -> dict[str, Any]:
        """What the wrapped source offers, minus the Plex identity."""
        offered = self.source()
        plex = offered.get("plex")
        if not isinstance(plex, dict):
            return offered

        kept = {key: value for key, value in plex.items() if key not in PLEX_IDENTITY}
        return (
            {**offered, "plex": kept}
            if kept
            else {key: value for key, value in offered.items() if key != "plex"}
        )


class LangfuseEnv(PydanticBaseSettingsSource):
    """The Langfuse section, read under Langfuse's own variable names.

    `MEDIASAGE_LANGFUSE__*` reaches the same fields through the normal nesting.
    This source exists so the keys a deployment already exports for the
    Langfuse SDK and CLI are picked up unchanged, from the environment or from
    `.env.langfuse`.
    """

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        """Never called: `__call__` is overridden and does not consult it."""
        raise NotImplementedError

    def __call__(self) -> dict[str, Any]:
        """The section these variables describe, or nothing if none is set."""
        offered = {**dotenv_values(LANGFUSE_ENV_PATH), **os.environ}
        section = {
            field: offered[name] for name, field in LANGFUSE_ENV.items() if offered.get(name)
        }
        return {"langfuse": section} if section else {}


class MediasageConfig(BaseSettings):
    """Root configuration object, loaded from YAML and the environment."""

    model_config = SettingsConfigDict(
        frozen=True,
        extra="ignore",
        env_prefix="MEDIASAGE_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    plex: PlexConfig = PlexConfig()
    # No default: an unconfigured provider fails at boot, not mid-request.
    llm: LLMSection
    budget: BudgetConfig = BudgetConfig()
    library: LibraryConfig = LibraryConfig()
    matching: MatchingConfig = MatchingConfig()
    recommend: RecommendConfig = RecommendConfig()
    research: ResearchConfig = ResearchConfig()
    art: ArtConfig = ArtConfig()
    defaults: DefaultsConfig = DefaultsConfig()
    langfuse: LangfuseConfig = LangfuseConfig()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Install the YAML source below the environment, minus Plex identity.

        Required: pydantic-settings ships no YAML source, and a `yaml_file` in
        `model_config` is ignored unless one is added here. YAML is not
        filtered — that is where a sign-in writes what it learned.
        """
        override = getattr(init_settings, "init_kwargs", {}).get("_base_config_file")
        base_path = Path(override) if override else BASE_CONFIG_PATH

        return (
            init_settings,
            Identityless(env_settings),
            Identityless(dotenv_settings),
            # Below the prefixed sources: an explicit `MEDIASAGE_` wins.
            LangfuseEnv(settings_cls),
            YamlConfigSettingsSource(
                settings_cls,
                yaml_file=[base_path, USER_CONFIG_PATH],
                deep_merge=True,
            ),
        )

    @classmethod
    def load(cls, config_path: Path | None = None) -> MediasageConfig:
        """Build the configuration from YAML files and the environment.

        Args:
            config_path: Base YAML file; defaults to `config.yaml`

        Returns:
            A fully resolved, validated configuration
        """
        if config_path is None:
            return cls()
        return cls(_base_config_file=config_path)
