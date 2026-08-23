"""Process-level configuration instance and persistence of UI-saved settings.

`ConfigStore` holds the single loaded `MediasageConfig` and writes changes made
through the UI to `config.user.yaml` so they survive a restart. Environment
variables still win on the next load — saving never overrides them.

A change is computed, written, and only then published: `candidate` builds what
an update would produce so a caller can prove it works first, and `commit`
keeps it. Nothing reaches memory that did not reach disk, and nothing skips
the gap between them where the caller probes.
"""

from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict

from backend.config import settings
from backend.config.models import LLM_SECTION_ADAPTER, ConfigUpdate, PlexConfig
from backend.config.settings import MediasageConfig


class ConfigSaveError(Exception):
    """Raised when configuration cannot be saved."""


class ConfigChange(BaseModel):
    """What an update would produce, computed but not yet kept.

    Handed out so a caller can connect to the server or spend a completion
    against the settings that are about to be written, rather than after.
    """

    model_config = ConfigDict(frozen=True)

    config: MediasageConfig
    # The sections to merge into `config.user.yaml`; empty writes nothing.
    sections: dict[str, Any] = {}

    @classmethod
    def of(cls, current: MediasageConfig, update: ConfigUpdate) -> Self:
        """What `update` would turn `current` into, without keeping it.

        Pure: nothing is written and nothing is published, so a caller may
        probe the result and walk away from it.

        Args:
            current: The configuration in force now
            update: The fields the caller wants changed

        Returns:
            The would-be configuration and the sections it writes
        """
        plex_changes = update.changes("plex")
        llm_changes: dict[str, Any] = {}
        if update.llm_provider:
            llm_changes.update(update.provider_changes)
        llm_changes.update(update.changes("llm"))

        return cls(
            config=current.model_copy(
                update={
                    "plex": PlexConfig(**(current.plex.model_dump() | plex_changes)),
                    "llm": LLM_SECTION_ADAPTER.validate_python(
                        current.llm.model_dump() | llm_changes
                    ),
                }
            ),
            sections={
                section: changes
                for section, changes in (("plex", plex_changes), ("llm", llm_changes))
                if changes
            },
        )

    @classmethod
    def to_plex(cls, current: MediasageConfig, changes: dict[str, Any]) -> Self:
        """What writing `changes` into the Plex section would produce.

        Separate from `of` because no form can express these: the address and
        both tokens come from a browser sign-in, not from `ConfigUpdate`.

        Args:
            current: The configuration in force now
            changes: Plex section keys, named as `PlexConfig` names them
        """
        # Unwrapped first: yaml writes a SecretStr as a python-object tag.
        plain = {key: ConfigUpdate.plain(value) for key, value in changes.items()}

        return cls(
            config=current.model_copy(
                update={"plex": PlexConfig(**(current.plex.model_dump() | plain))}
            ),
            sections={"plex": plain} if plain else {},
        )


class ConfigStore:
    """Owns the loaded configuration and the file UI edits are written to.

    A plain class, not a model: `get` is depended on directly by the routes,
    and a bound method of an unfrozen pydantic model is unhashable.
    """

    def __init__(self, user_config_path: Path | None = None) -> None:
        """
        Args:
            user_config_path: Where UI edits are written; the default location
                is resolved late, so a test may redirect it instead
        """
        self.user_config_path = user_config_path
        self.config: MediasageConfig | None = None

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

    def candidate(self, update: ConfigUpdate) -> ConfigChange:
        """What `update` would produce against what is loaded now."""
        return ConfigChange.of(self.get(), update)

    def commit(self, change: ConfigChange) -> MediasageConfig:
        """Write a change, then publish it in memory.

        In that order: a failed write must not leave the process running on
        settings that are not on disk and will not survive a restart.

        Raises:
            ConfigSaveError: If the file cannot be written; nothing is published
        """
        if change.sections:
            self.save(change.sections)

        self.config = change.config
        return self.config

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
