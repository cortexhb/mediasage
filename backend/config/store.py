"""Process-level configuration instance and persistence of UI-saved settings.

`ConfigStore` holds the single loaded `MediasageConfig` and writes changes made
through the UI to `config.user.yaml` so they survive a restart. Environment
variables still win on the next load — saving never overrides them.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from backend.config import settings
from backend.config.models import LLM_SECTION_ADAPTER, ConfigUpdate, PlexConfig
from backend.config.settings import MediasageConfig


class ConfigSaveError(Exception):
    """Raised when configuration cannot be saved."""


class ConfigStore(BaseModel):
    """Owns the loaded configuration and the file UI edits are written to."""

    model_config = ConfigDict(validate_assignment=True)

    user_config_path: Path | None = None
    config: MediasageConfig | None = None

    @property
    def path(self) -> Path:
        """Where UI-saved settings live, resolved late so tests can redirect it."""
        return self.user_config_path or settings.USER_CONFIG_PATH

    def get(self) -> MediasageConfig:
        """Return the current configuration, loading it on first use."""
        if self.config is None:
            self.config = MediasageConfig.load()
        return self.config

    def refresh(self, config_path: Path | None = None) -> MediasageConfig:
        """Reload configuration from file and environment."""
        self.config = MediasageConfig.load(config_path)
        return self.config

    def apply(self, update: ConfigUpdate) -> MediasageConfig:
        """Apply a change from the UI and persist it.

        Args:
            update: The fields the caller wants changed

        Returns:
            The updated configuration
        """
        current = self.get()

        plex_changes = update.changes("plex")
        llm_changes: dict[str, Any] = {}
        if update.llm_provider:
            llm_changes.update(self.provider_changes(update))
        llm_changes.update(update.changes("llm"))

        self.config = current.model_copy(
            update={
                "plex": PlexConfig(**(current.plex.model_dump() | plex_changes)),
                "llm": LLM_SECTION_ADAPTER.validate_python(
                    current.llm.model_dump() | llm_changes
                ),
            }
        )

        sections = {
            section: changes
            for section, changes in (("plex", plex_changes), ("llm", llm_changes))
            if changes
        }
        if sections:
            self.save(sections)

        return self.config

    @staticmethod
    def provider_changes(update: ConfigUpdate) -> dict[str, Any]:
        """Clear what belonged to the previous provider.

        Model names, endpoints and prices do not survive a provider switch: they
        name things the new provider does not serve. Anything the caller supplied
        explicitly is left for `changes` to apply over the top.

        `context_window` is deliberately kept: it is required, so blanking it
        would leave the section unvalidatable until the user supplies a new one.
        """
        derived: dict[str, Any] = {"provider": update.llm_provider}

        for field, supplied, blank in (
            ("model_analysis", update.model_analysis, ""),
            ("model_generation", update.model_generation, ""),
            ("endpoint_url", update.endpoint_url, ""),
            ("cost_analysis_input", update.cost_analysis_input, 0.0),
            ("cost_analysis_output", update.cost_analysis_output, 0.0),
            ("cost_generation_input", update.cost_generation_input, 0.0),
            ("cost_generation_output", update.cost_generation_output, 0.0),
        ):
            if not supplied:
                derived[field] = blank

        return derived

    def read_user_yaml(self) -> dict[str, Any]:
        """Read the UI-saved settings file, empty when it does not exist."""
        if not self.path.exists():
            return {}
        with self.path.open() as f:
            return yaml.safe_load(f) or {}

    def save(self, sections: dict[str, Any]) -> None:
        """Merge sections into `config.user.yaml` and write it back.

        Args:
            sections: Nested mapping of section name to changed keys

        Raises:
            ConfigSaveError: If the file cannot be written
        """
        cleaned = self.prune(self.deep_merge(self.read_user_yaml(), sections))

        try:
            with self.path.open("w") as f:
                yaml.dump(cleaned, f, default_flow_style=False)
        except PermissionError:
            raise ConfigSaveError(
                f"Permission denied writing to {self.path}. "
                "Check that the data directory is writable. "
                "For Docker, ensure the volume is mounted with correct permissions "
                "(e.g., user directive or chown to UID 1000)."
            ) from None
        except OSError as e:
            raise ConfigSaveError(
                f"Failed to save configuration to {self.path}: {e}. "
                "Check disk space and directory permissions."
            ) from e

    @classmethod
    def deep_merge(cls, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Recursively merge override into base, returning a new dict."""
        result = base.copy()
        for key, value in override.items():
            if isinstance(result.get(key), dict) and isinstance(value, dict):
                result[key] = cls.deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    @classmethod
    def prune(cls, mapping: dict[str, Any]) -> dict[str, Any]:
        """Drop keys whose value is None or empty, recursively.

        Keeps the saved file free of blanks that would shadow a default.
        """
        result: dict[str, Any] = {}
        for key, value in mapping.items():
            if isinstance(value, dict):
                nested = cls.prune(value)
                if nested:
                    result[key] = nested
            elif value not in (None, ""):
                result[key] = value
        return result


# The single instance the application reads and writes through.
config_store = ConfigStore()
