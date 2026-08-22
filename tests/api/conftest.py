"""Fixtures for the HTTP layer: an application, and the stores behind it.

Every guard reads its store through `backend.api.guards`, so that is the one
place a test patches to say what the application can reach.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.config import (
    LLM_SECTION_ADAPTER,
    BudgetConfig,
    DefaultsConfig,
    MediasageConfig,
    PlexConfig,
)

# Local providers are reached by URL and must carry one; cloud ones must not.
LOCAL_PROVIDERS = ("ollama", "custom")


def mediasage_config(
    plex_url: str = "http://test:32400",
    plex_token: str = "token",
    music_library: str = "Music",
    llm_provider: str = "anthropic",
    llm_api_key: str = "key",
    model_analysis: str = "claude-sonnet-4-5",
    model_generation: str = "claude-haiku-4-5",
    track_count: int = 25,
    endpoint_url: str = "http://localhost:11434",
    context_window: int = 32768,
) -> MediasageConfig:
    """A real config, so budgeting and pricing arithmetic works on it."""
    llm: dict[str, object] = {
        "provider": llm_provider,
        "api_key": llm_api_key,
        "model_analysis": model_analysis,
        "model_generation": model_generation,
        "context_window": context_window,
    }
    if llm_provider in LOCAL_PROVIDERS:
        llm["endpoint_url"] = endpoint_url

    return MediasageConfig(
        plex=PlexConfig(url=plex_url, token=plex_token, music_library=music_library),
        llm=LLM_SECTION_ADAPTER.validate_python(llm),
        budget=BudgetConfig(),
        defaults=DefaultsConfig(track_count=track_count),
    )


def connected_plex(**attributes) -> MagicMock:
    """A Plex client that reports itself connected."""
    plex = MagicMock(**attributes)
    plex.is_connected.return_value = True
    return plex


def plex_store_of(client: object | None) -> MagicMock:
    """A stand-in for `plex_store` whose `get()` returns `client`.

    For a test that installs its own patches rather than taking the `plex`
    fixture -- the setup wizard's, which also need `init` absorbed.
    """
    store = MagicMock()
    store.get.return_value = client
    return store


@pytest.fixture
def client() -> TestClient:
    """A test client over a freshly built application.

    Built per test rather than shared: `create_app` mounts routes, and a test
    that changes what is mounted must not leak into the next one.
    """
    return TestClient(create_app())


@pytest.fixture
def plex(request):
    """Patch the Plex store to hand back `request.param`, or a connected client.

    Patching the store rather than the client also absorbs the `init()` calls
    that the config and setup endpoints make.
    """
    # `hasattr`, not a default: None is a meaningful parameter here -- it is
    # how a test says nothing is configured at all.
    client = request.param if hasattr(request, "param") else connected_plex()

    store = MagicMock()
    store.get.return_value = client
    with patch("backend.api.guards.plex_store", store):
        yield client
