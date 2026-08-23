"""Top-level configuration model and the sources it loads from.

`MediasageConfig` owns the loading concern. YAML is the ground source; every
setting is also reachable from the environment under one prefix, so nothing
needs a per-field name table.

Precedence, highest first:

1. Values passed to the constructor
2. `MEDIASAGE_*` environment variables
3. `.env`
4. `data/config.user.yaml` — settings saved from the UI
5. `config.yaml` — the deployment's base file
6. Field defaults

Section fields nest with a double underscore: `MEDIASAGE_PLEX__URL`,
`MEDIASAGE_LLM__ENDPOINT_URL`, `MEDIASAGE_DEFAULTS__TRACK_COUNT`.
"""

from pathlib import Path

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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Install the YAML source below the environment.

        Required: pydantic-settings ships no YAML source, and a `yaml_file` in
        `model_config` is ignored unless one is added here.
        """
        override = getattr(init_settings, "init_kwargs", {}).get("_base_config_file")
        base_path = Path(override) if override else BASE_CONFIG_PATH

        return (
            init_settings,
            env_settings,
            dotenv_settings,
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
