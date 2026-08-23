"""Tests for the configuration store: persistence and in-place updates."""

import pytest
import yaml

from backend.config import (
    ConfigSaveError,
    ConfigStore,
    ConfigUpdate,
    LocalLLMConfig,
    MediasageConfig,
)


class TestReadUserYaml:
    """Tests for reading the UI-saved settings file."""

    def test_reads_valid_yaml(self, tmp_path):
        """Should load a valid YAML config file."""
        path = tmp_path / "config.user.yaml"
        config_data = {
            "plex": {"url": "http://localhost:32400", "token": "test-token"},
            "llm": {"provider": "anthropic", "api_key": "sk-test"},
        }
        path.write_text(yaml.dump(config_data))

        result = ConfigStore(user_config_path=path).read_user_yaml()

        assert result["plex"]["url"] == "http://localhost:32400"
        assert result["llm"]["provider"] == "anthropic"

    def test_returns_empty_dict_for_missing_file(self, tmp_path):
        """Should return empty dict when config file doesn't exist."""
        path = tmp_path / "nonexistent.yaml"

        result = ConfigStore(user_config_path=path).read_user_yaml()

        assert result == {}

    def test_returns_empty_dict_for_empty_file(self, tmp_path):
        """Should return empty dict for empty config file."""
        path = tmp_path / "config.user.yaml"
        path.write_text("")

        result = ConfigStore(user_config_path=path).read_user_yaml()

        assert result == {}


class TestDeepMerge:
    """Tests for the deep_merge helper."""

    def test_merges_flat_dicts(self):
        """Should merge flat dictionaries."""
        base = {"a": 1, "b": 2}
        override = {"b": 20, "c": 3}

        result = ConfigStore.deep_merge(base, override)

        assert result == {"a": 1, "b": 20, "c": 3}

    def test_merges_nested_dicts(self):
        """Should recursively merge nested dictionaries."""
        base = {"a": {"b": 1, "c": 2}, "d": 4}
        override = {"a": {"b": 10}}

        result = ConfigStore.deep_merge(base, override)

        assert result == {"a": {"b": 10, "c": 2}, "d": 4}

    def test_override_replaces_non_dict_with_dict(self):
        """Should replace non-dict value with dict if override is dict."""
        base = {"a": 1}
        override = {"a": {"nested": True}}

        result = ConfigStore.deep_merge(base, override)

        assert result == {"a": {"nested": True}}

    def test_does_not_modify_original(self):
        """Should not modify the original dictionaries."""
        base = {"a": {"b": 1}}
        override = {"a": {"c": 2}}

        ConfigStore.deep_merge(base, override)

        assert base == {"a": {"b": 1}}
        assert override == {"a": {"c": 2}}


class TestPrune:
    """Tests for the prune helper."""

    def test_removes_empty_strings(self):
        """Should remove keys with empty string values."""
        d = {"a": "", "b": "value", "c": ""}

        assert ConfigStore.prune(d) == {"b": "value"}

    def test_removes_none_values(self):
        """Should remove keys with None values."""
        d = {"a": None, "b": "value", "c": None}

        assert ConfigStore.prune(d) == {"b": "value"}

    def test_preserves_other_falsy_values(self):
        """Should preserve 0 and False values."""
        d = {"a": 0, "b": False, "c": "value"}

        assert ConfigStore.prune(d) == {"a": 0, "b": False, "c": "value"}

    def test_removes_empty_nested_dicts(self):
        """Should remove nested dicts that become empty."""
        d = {"a": {"b": "", "c": None}, "d": "value"}

        assert ConfigStore.prune(d) == {"d": "value"}

    def test_preserves_non_empty_nested_dicts(self):
        """Should preserve nested dicts with values."""
        d = {"a": {"b": "", "c": "nested"}, "d": "value"}

        assert ConfigStore.prune(d) == {"a": {"c": "nested"}, "d": "value"}


class TestSave:
    """Tests for writing UI-saved settings."""

    def test_writes_and_merges_sections(self, tmp_path):
        """Should merge new sections into whatever the file already holds."""
        path = tmp_path / "config.user.yaml"
        path.write_text(yaml.dump({"plex": {"token": "old"}, "llm": {"provider": "openai"}}))
        store = ConfigStore(user_config_path=path)

        store.save({"plex": {"url": "http://new:32400"}})

        written = yaml.safe_load(path.read_text())
        assert written["plex"] == {"token": "old", "url": "http://new:32400"}
        assert written["llm"] == {"provider": "openai"}

    def test_blank_values_are_not_written(self, tmp_path):
        """Should keep the saved file free of blanks that shadow defaults."""
        path = tmp_path / "config.user.yaml"
        store = ConfigStore(user_config_path=path)

        store.save({"plex": {"url": "http://new:32400", "token": ""}})

        assert yaml.safe_load(path.read_text()) == {"plex": {"url": "http://new:32400"}}

    def test_raises_config_save_error_when_unwritable(self, tmp_path):
        """Should raise ConfigSaveError rather than a bare OSError."""
        store = ConfigStore(user_config_path=tmp_path / "missing-dir" / "config.user.yaml")

        with pytest.raises(ConfigSaveError):
            store.save({"plex": {"url": "http://new:32400"}})


# The smallest loadable llm section; these tests are about the plex half.
LLM = {"provider": "openai", "context_window": 128_000}


def store_over(tmp_path, config_data) -> ConfigStore:
    """A store holding `config_data`, writing user edits inside `tmp_path`."""
    base = tmp_path / "config.yaml"
    base.write_text(yaml.dump(config_data))
    store = ConfigStore(user_config_path=tmp_path / "config.user.yaml")
    store.config = MediasageConfig.load(base)
    return store


def applied(store: ConfigStore, update: ConfigUpdate) -> MediasageConfig:
    """Compute a change and keep it, the way a route does minus the probe.

    Local to the tests: production never runs the two back to back, it proves
    the candidate works in between.
    """
    return store.commit(store.candidate(update))


class TestApply:
    """Tests for applying an update from the UI."""

    def test_updates_plex_and_persists(self, tmp_path, clean_config_env):
        """Should update the in-memory config and write the change out."""
        store = store_over(
            tmp_path,
            {
                "plex": {"url": "http://old:32400", "token": "tok"},
                "llm": {"provider": "openai", "context_window": 128_000},
            },
        )

        config = applied(store, ConfigUpdate(plex_url="http://new:32400"))

        assert config.plex.url == "http://new:32400"
        assert config.plex.token.get_secret_value() == "tok"
        assert yaml.safe_load(store.path.read_text())["plex"] == {"url": "http://new:32400"}

    def test_provider_switch_clears_the_previous_models(self, tmp_path, clean_config_env):
        """The old provider's model names do not survive; nothing is guessed in their place."""
        store = store_over(
            tmp_path,
            {
                "llm": {
                    "provider": "anthropic",
                    "model_analysis": "claude-old",
                    "context_window": 200_000,
                }
            },
        )

        config = applied(store, ConfigUpdate(llm_provider="openai"))

        assert config.llm.provider == "openai"
        assert config.llm.model_analysis == ""
        assert config.llm.model_generation == ""

    def test_explicit_model_survives_a_provider_switch(self, tmp_path, clean_config_env):
        """An explicitly supplied model should be kept."""
        store = store_over(tmp_path, {"llm": {"provider": "anthropic", "context_window": 200_000}})

        config = applied(store, ConfigUpdate(llm_provider="openai", model_analysis="gpt-mine"))

        assert config.llm.model_analysis == "gpt-mine"
        assert config.llm.model_generation == ""

    def test_switching_to_a_local_provider_builds_the_local_section(
        self, tmp_path, clean_config_env
    ):
        """A provider switch changes which section class holds the settings."""
        store = store_over(tmp_path, {"llm": {"provider": "openai", "context_window": 128_000}})

        config = applied(
            store,
            ConfigUpdate(
                llm_provider="custom",
                endpoint_url="http://localhost:5000/v1",
                context_window=8192,
            ),
        )

        llm = config.llm

        assert isinstance(llm, LocalLLMConfig)
        assert llm.is_local is True
        assert llm.endpoint_url == "http://localhost:5000/v1"
        assert llm.context_window == 8192

    def test_nothing_is_written_when_update_is_empty(self, tmp_path, clean_config_env):
        """An empty update should leave the file untouched."""
        store = store_over(
            tmp_path,
            {
                "plex": {"url": "http://old:32400"},
                "llm": {"provider": "openai", "context_window": 128_000},
            },
        )

        applied(store, ConfigUpdate())

        assert not store.path.exists()


class TestCandidate:
    """A candidate is computed without keeping it."""

    def test_nothing_is_written(self, tmp_path, clean_config_env):
        store = store_over(tmp_path, {"plex": {"url": "http://old:32400"}, "llm": LLM})

        store.candidate(ConfigUpdate(plex_url="http://new:32400"))

        assert not store.path.exists()

    def test_nothing_is_published(self, tmp_path, clean_config_env):
        """The held configuration is untouched until the change is committed."""
        store = store_over(tmp_path, {"plex": {"url": "http://old:32400"}, "llm": LLM})

        store.candidate(ConfigUpdate(plex_url="http://new:32400"))

        assert store.get().plex.url == "http://old:32400"

    def test_the_change_carries_what_it_would_write(self, tmp_path, clean_config_env):
        store = store_over(tmp_path, {"plex": {"url": "http://old:32400"}, "llm": LLM})

        change = store.candidate(ConfigUpdate(plex_url="http://new:32400"))

        assert change.config.plex.url == "http://new:32400"
        assert change.sections == {"plex": {"url": "http://new:32400"}}

    def test_an_empty_update_writes_no_section(self, tmp_path, clean_config_env):
        store = store_over(tmp_path, {"plex": {"url": "http://old:32400"}, "llm": LLM})

        assert store.candidate(ConfigUpdate()).sections == {}


class TestCommit:
    """The write happens before the change reaches memory."""

    def test_a_failed_write_publishes_nothing(self, tmp_path, clean_config_env):
        """Otherwise the process runs on settings that will not survive a restart."""
        store = store_over(tmp_path, {"plex": {"url": "http://old:32400"}, "llm": LLM})
        change = store.candidate(ConfigUpdate(plex_url="http://new:32400"))
        store.user_config_path = tmp_path / "missing-dir" / "config.user.yaml"

        with pytest.raises(ConfigSaveError):
            store.commit(change)

        assert store.get().plex.url == "http://old:32400"

    def test_a_written_change_is_published(self, tmp_path, clean_config_env):
        store = store_over(tmp_path, {"plex": {"url": "http://old:32400"}, "llm": LLM})

        store.commit(store.candidate(ConfigUpdate(plex_url="http://new:32400")))

        assert store.get().plex.url == "http://new:32400"
