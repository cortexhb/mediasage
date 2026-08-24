"""The Langfuse section, from Langfuse's own variable names.

`LangfuseEnv` exists so the keys a deployment already exports for the Langfuse
SDK reach the section unchanged. These pin that, and that a `MEDIASAGE_`
variable still wins over one of them.
"""

from backend.config import MediasageConfig
from backend.config import settings as config_settings

LLM = {"provider": "anthropic", "context_window": 200000}


class TestLangfuseEnv:
    def test_nothing_set_leaves_tracing_off(self):
        assert MediasageConfig(llm=LLM).langfuse.is_configured is False

    def test_langfuse_names_reach_the_section(self, monkeypatch):
        monkeypatch.setenv("LANGFUSE_BASE_URL", "https://langfuse.example")
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-env")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-env")

        section = MediasageConfig(llm=LLM).langfuse

        assert section.is_configured is True
        assert section.public_key == "pk-lf-env"
        assert section.secret_key.get_secret_value() == "sk-lf-env"

    def test_the_tracing_environment_is_read(self, monkeypatch):
        monkeypatch.setenv("LANGFUSE_TRACING_ENVIRONMENT", "staging")

        assert MediasageConfig(llm=LLM).langfuse.environment == "staging"

    def test_the_prefixed_name_wins(self, monkeypatch):
        """A `MEDIASAGE_` variable is the explicit one, so it takes precedence."""
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-plain")
        monkeypatch.setenv("MEDIASAGE_LANGFUSE__PUBLIC_KEY", "pk-lf-prefixed")

        assert MediasageConfig(llm=LLM).langfuse.public_key == "pk-lf-prefixed"

    def test_the_env_file_is_read(self, monkeypatch, tmp_path):
        """The keys are mounted as `.env.langfuse`, not exported."""
        env_file = tmp_path / ".env.langfuse"
        env_file.write_text("LANGFUSE_PUBLIC_KEY=pk-lf-file\n")
        monkeypatch.setattr(config_settings, "LANGFUSE_ENV_PATH", env_file)

        assert MediasageConfig(llm=LLM).langfuse.public_key == "pk-lf-file"

    def test_the_secret_key_does_not_print(self, monkeypatch):
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-secret")

        assert "sk-lf-secret" not in repr(MediasageConfig(llm=LLM).langfuse)
