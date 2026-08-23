"""Tests for configuration loading and source precedence."""

import pytest
import yaml
from pydantic import SecretStr, ValidationError

from backend.config import LocalLLMConfig, MediasageConfig

# Minimum a config file must carry for the LLM section to validate.
# Every provider must declare a window; these tests only care that it is set.
CLOUD_LLM = {"provider": "openai", "context_window": 128_000}
LOCAL_LLM = {
    "provider": "custom",
    "endpoint_url": "http://localhost:5000/v1",
    "context_window": 8192,
}


def write_config(tmp_path, data):
    """Write a base config file and return its path."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(data))
    return config_file


def plain(value):
    """A loaded field as its value, whether or not it is a secret."""
    return value.get_secret_value() if isinstance(value, SecretStr) else value


class TestSourcePrecedence:
    """Tests for environment variable priority over YAML."""

    def test_env_var_takes_priority(self, tmp_path, clean_config_env):
        """Environment variable should override YAML value."""
        config_file = write_config(tmp_path, {"plex": {"music_library": "Yaml"}, "llm": CLOUD_LLM})
        clean_config_env.setenv("MEDIASAGE_PLEX__MUSIC_LIBRARY", "Env")

        assert MediasageConfig.load(config_file).plex.music_library == "Env"

    def test_yaml_used_when_no_env_var(self, tmp_path, clean_config_env):
        """YAML value should be used when env var not set."""
        config_file = write_config(tmp_path, {"plex": {"music_library": "Yaml"}, "llm": CLOUD_LLM})

        assert MediasageConfig.load(config_file).plex.music_library == "Yaml"

    def test_default_used_when_no_env_or_yaml(self, tmp_path, clean_config_env):
        """Default should be used when neither env nor YAML set."""
        config_file = write_config(tmp_path, {"llm": CLOUD_LLM})

        assert MediasageConfig.load(config_file).plex.music_library == "Music"

    def test_empty_string_env_var_is_used(self, tmp_path, clean_config_env):
        """Empty string env var should still take priority."""
        config_file = write_config(
            tmp_path, {"llm": CLOUD_LLM | {"model_generation": "gpt-4o-mini"}}
        )
        clean_config_env.setenv("MEDIASAGE_LLM__MODEL_GENERATION", "")

        assert MediasageConfig.load(config_file).llm.model_generation == ""


class TestPlexIdentityIsNotEnvironmental:
    """A sign-in writes it to YAML; no variable may supply or shadow it.

    Set from the environment, a stale address would outrank the one the last
    sign-in resolved, and no save could correct it.
    """

    @pytest.mark.parametrize(
        ("variable", "field"),
        [
            ("MEDIASAGE_PLEX__URL", "url"),
            ("MEDIASAGE_PLEX__TOKEN", "token"),
            ("MEDIASAGE_PLEX__ACCOUNT_TOKEN", "account_token"),
            ("MEDIASAGE_PLEX__SERVER_ID", "server_id"),
            ("MEDIASAGE_PLEX__SERVER_NAME", "server_name"),
            ("MEDIASAGE_PLEX__CLIENT_ID", "client_id"),
        ],
    )
    def test_an_identity_env_var_is_ignored(self, tmp_path, clean_config_env, variable, field):
        config_file = write_config(tmp_path, {"plex": {field: "from-yaml"}, "llm": CLOUD_LLM})
        clean_config_env.setenv(variable, "from-env")

        loaded = getattr(MediasageConfig.load(config_file).plex, field)

        assert plain(loaded) == "from-yaml"

    def test_a_plex_only_environment_leaves_the_section_defaulted(self, tmp_path, clean_config_env):
        """Dropping every key must drop the section, not offer an empty one."""
        config_file = write_config(
            tmp_path, {"plex": {"url": "http://yaml:32400"}, "llm": CLOUD_LLM}
        )
        clean_config_env.setenv("MEDIASAGE_PLEX__TOKEN", "from-env")

        assert MediasageConfig.load(config_file).plex.url == "http://yaml:32400"

    def test_a_non_identity_plex_var_still_works(self, tmp_path, clean_config_env):
        """Only the identity is filtered; the rest of the section is settable."""
        config_file = write_config(tmp_path, {"llm": CLOUD_LLM})
        clean_config_env.setenv("MEDIASAGE_PLEX__MUSIC_LIBRARY", "Env")
        clean_config_env.setenv("MEDIASAGE_PLEX__TOKEN", "from-env")

        loaded = MediasageConfig.load(config_file).plex

        assert (loaded.music_library, plain(loaded.token)) == ("Env", "")


class TestUnconfiguredProvider:
    """An unconfigured LLM must fail at load, not part-way through a request."""

    def test_missing_llm_section_is_rejected(self, tmp_path, clean_config_env):
        """A config with no LLM section should refuse to load."""
        config_file = write_config(tmp_path, {"plex": {"url": "http://plex:32400"}})

        with pytest.raises(ValidationError):
            MediasageConfig.load(config_file)

    def test_missing_provider_is_rejected(self, tmp_path, clean_config_env):
        """An LLM section without a provider should refuse to load."""
        config_file = write_config(tmp_path, {"llm": {"api_key": "sk-test"}})

        with pytest.raises(ValidationError):
            MediasageConfig.load(config_file)

    def test_unknown_provider_is_rejected(self, tmp_path, clean_config_env):
        """A provider outside the supported set should refuse to load."""
        config_file = write_config(
            tmp_path, {"llm": {"provider": "notaprovider", "context_window": 128_000}}
        )

        with pytest.raises(ValidationError):
            MediasageConfig.load(config_file)

    def test_local_provider_without_endpoint_is_rejected(self, tmp_path, clean_config_env):
        """A local provider is useless without a URL to call."""
        config_file = write_config(
            tmp_path, {"llm": {"provider": "custom", "context_window": 8192}}
        )

        with pytest.raises(ValidationError):
            MediasageConfig.load(config_file)

    def test_local_provider_without_context_window_is_rejected(self, tmp_path, clean_config_env):
        """Prompts cannot be sized without knowing the window."""
        config_file = write_config(
            tmp_path, {"llm": {"provider": "custom", "endpoint_url": "http://host:5000/v1"}}
        )

        with pytest.raises(ValidationError):
            MediasageConfig.load(config_file)


class TestLoadConfig:
    """Tests for full configuration loading."""

    def test_loads_from_yaml_file(self, tmp_path, clean_config_env):
        """Should load configuration from YAML file."""
        config_file = write_config(
            tmp_path,
            {
                "plex": {
                    "url": "http://plex.local:32400",
                    "token": "yaml-token",
                    "music_library": "My Music",
                },
                "llm": {
                    "provider": "anthropic",
                    "api_key": "sk-yaml-key",
                    "context_window": 200_000,
                },
                "defaults": {"track_count": 40},
            },
        )

        config = MediasageConfig.load(config_file)

        assert config.plex.url == "http://plex.local:32400"
        assert config.plex.token.get_secret_value() == "yaml-token"
        assert config.plex.music_library == "My Music"
        assert config.llm.provider == "anthropic"
        assert config.llm.api_key.get_secret_value() == "sk-yaml-key"
        assert config.defaults.track_count == 40

    def test_env_vars_override_yaml(self, tmp_path, clean_config_env):
        """Environment variables should override YAML values."""
        config_file = write_config(
            tmp_path,
            {
                "plex": {"url": "http://yaml:32400", "token": "yaml-token"},
                "llm": {"provider": "anthropic", "api_key": "yaml-key", "context_window": 200_000},
            },
        )

        clean_config_env.setenv("MEDIASAGE_PLEX__MUSIC_LIBRARY", "Env Music")
        clean_config_env.setenv("MEDIASAGE_LLM__API_KEY", "env-key")

        config = MediasageConfig.load(config_file)

        assert config.plex.music_library == "Env Music"
        assert config.llm.api_key.get_secret_value() == "env-key"

    def test_api_key_is_provider_independent(self, tmp_path, clean_config_env):
        """One key serves whichever provider is selected."""
        config_file = write_config(
            tmp_path, {"llm": {"provider": "anthropic", "context_window": 200_000}}
        )
        clean_config_env.setenv("MEDIASAGE_LLM__API_KEY", "the-key")

        assert MediasageConfig.load(config_file).llm.api_key.get_secret_value() == "the-key"

        config_file = write_config(
            tmp_path, {"llm": {"provider": "openai", "context_window": 128_000}}
        )

        assert MediasageConfig.load(config_file).llm.api_key.get_secret_value() == "the-key"

    def test_models_are_not_guessed(self, tmp_path, clean_config_env):
        """A provider named without models leaves them blank rather than guessing."""
        config_file = write_config(
            tmp_path, {"llm": {"provider": "openai", "context_window": 128_000}}
        )

        config = MediasageConfig.load(config_file)

        assert config.llm.model_analysis == ""
        assert config.llm.model_generation == ""

    def test_configured_models_are_kept(self, tmp_path, clean_config_env):
        """Model settings come from configuration, and only from there."""
        config_file = write_config(
            tmp_path,
            {
                "llm": {
                    "provider": "anthropic",
                    "context_window": 200_000,
                    "api_key": "test",
                    "model_analysis": "custom-analysis-model",
                    "model_generation": "custom-gen-model",
                }
            },
        )

        config = MediasageConfig.load(config_file)

        assert config.llm.model_analysis == "custom-analysis-model"
        assert config.llm.model_generation == "custom-gen-model"

    def test_plex_defaults_applied_when_absent(self, tmp_path, clean_config_env):
        """Plex and UI sections still have defaults; only the LLM is never guessed."""
        config_file = write_config(tmp_path, {"llm": CLOUD_LLM})

        config = MediasageConfig.load(config_file)

        assert config.plex.music_library == "Music"
        assert config.defaults.track_count == 25

    def test_user_config_overrides_base_file(
        self, tmp_path, clean_config_env, isolated_user_config
    ):
        """UI-saved settings should win over the deployment's base file."""
        config_file = write_config(
            tmp_path,
            {"plex": {"url": "http://base:32400", "token": "base"}, "llm": CLOUD_LLM},
        )
        isolated_user_config.write_text(yaml.dump({"plex": {"url": "http://user:32400"}}))

        config = MediasageConfig.load(config_file)

        assert config.plex.url == "http://user:32400"
        assert config.plex.token.get_secret_value() == "base"

    def test_secrets_are_stored_as_given(self, tmp_path, clean_config_env):
        """Tokens and keys round-trip unchanged."""
        config_file = write_config(
            tmp_path,
            {
                "plex": {"url": "http://test:32400", "token": "secret-token"},
                "llm": {
                    "provider": "anthropic",
                    "api_key": "secret-api-key",
                    "context_window": 200_000,
                },
            },
        )

        config = MediasageConfig.load(config_file)

        assert config.plex.token.get_secret_value() == "secret-token"
        assert config.llm.api_key.get_secret_value() == "secret-api-key"


class TestLocalProviderConfig:
    """Tests for local LLM provider configuration."""

    def test_loads_ollama_config_from_yaml(self, tmp_path, clean_config_env):
        """Should load Ollama config from YAML file."""
        config_file = write_config(
            tmp_path,
            {
                "llm": {
                    "provider": "ollama",
                    "endpoint_url": "http://192.168.1.100:11434",
                    "context_window": 32768,
                    "model_analysis": "llama3:8b",
                    "model_generation": "llama3:8b",
                }
            },
        )

        config = MediasageConfig.load(config_file)

        assert config.llm.provider == "ollama"
        assert config.llm.endpoint_url == "http://192.168.1.100:11434"
        assert config.llm.model_analysis == "llama3:8b"
        assert config.llm.is_local is True

    def test_endpoint_url_env_var_override(self, tmp_path, clean_config_env):
        """The endpoint env var should override the YAML value."""
        config_file = write_config(
            tmp_path,
            {
                "llm": {
                    "provider": "ollama",
                    "endpoint_url": "http://yaml-host:11434",
                    "context_window": 32768,
                }
            },
        )

        clean_config_env.setenv("MEDIASAGE_LLM__ENDPOINT_URL", "http://env-host:11434")

        llm = MediasageConfig.load(config_file).llm

        assert isinstance(llm, LocalLLMConfig)
        assert llm.endpoint_url == "http://env-host:11434"

    def test_loads_custom_provider_config(self, tmp_path, clean_config_env):
        """Should load custom provider config from YAML."""
        config_file = write_config(
            tmp_path,
            {
                "llm": {
                    "provider": "custom",
                    "endpoint_url": "http://localhost:5000/v1",
                    "context_window": 8192,
                    "model_analysis": "my-model",
                    "model_generation": "my-model",
                }
            },
        )

        config = MediasageConfig.load(config_file)

        assert config.llm.provider == "custom"
        assert config.llm.endpoint_url == "http://localhost:5000/v1"
        assert config.llm.context_window == 8192

    def test_context_window_env_var(self, tmp_path, clean_config_env):
        """The context window env var should override YAML."""
        config_file = write_config(tmp_path, {"llm": LOCAL_LLM})

        clean_config_env.setenv("MEDIASAGE_LLM__CONTEXT_WINDOW", "16384")

        assert MediasageConfig.load(config_file).llm.context_window == 16384

    def test_cloud_provider_is_not_local(self, tmp_path, clean_config_env):
        """A hosted provider carries no endpoint or window."""
        config_file = write_config(tmp_path, {"llm": CLOUD_LLM})

        config = MediasageConfig.load(config_file)

        assert config.llm.is_local is False
        assert not hasattr(config.llm, "endpoint_url")
