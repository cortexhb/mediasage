"""Fixtures shared by the configuration tests."""

import pytest

from backend.config import MediasageConfig, settings
from backend.config.store import config_store


@pytest.fixture(autouse=True)
def unloaded_store(monkeypatch):
    """Undo the root fixture: these tests assert on loading, not on a loaded one."""
    monkeypatch.setattr(config_store, "config", None)


@pytest.fixture(autouse=True)
def isolated_user_config(tmp_path, monkeypatch):
    """Point UI-saved settings at a scratch file so the real one is never read."""
    path = tmp_path / "config.user.yaml"
    monkeypatch.setattr(settings, "USER_CONFIG_PATH", path)
    return path


@pytest.fixture(autouse=True)
def no_developer_dotenv(monkeypatch):
    """Ignore the repository .env; tests assert against values they set."""
    config = dict(MediasageConfig.model_config)
    config["env_file"] = None
    monkeypatch.setattr(MediasageConfig, "model_config", config)
