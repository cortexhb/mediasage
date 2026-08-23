"""Fixtures for the HTTP layer: an application, and what its routes resolve.

A route declares its dependencies, so a test says what the application can
reach by overriding them on the app rather than by patching a module. Rebuilds
are absorbed for every test: saving settings must never open a real connection.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.config import (
    LLM_SECTION_ADAPTER,
    BudgetConfig,
    DefaultsConfig,
    MediasageConfig,
    PlexConfig,
    config_store,
)
from backend.llm import LLMClient, ModelListing
from backend.plex import PlexClient, PlexNotConnected, plex_store

# Local providers are reached by URL and must carry one; cloud ones must not.
LOCAL_PROVIDERS = ("ollama", "custom")


def mediasage_config(
    plex_url: str = "http://test:32400",
    plex_token: str = "token",
    account_token: str = "account-token",
    server_id: str = "abc123",
    server_name: str = "Test Server",
    client_id: str = "test-client-id",
    music_library: str = "Music",
    llm_provider: str = "anthropic",
    llm_api_key: str = "key",
    model_analysis: str = "claude-sonnet-4-5",
    model_generation: str = "claude-haiku-4-5",
    smart_generation: bool = False,
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
        "smart_generation": smart_generation,
        "context_window": context_window,
    }
    if llm_provider in LOCAL_PROVIDERS:
        llm["endpoint_url"] = endpoint_url

    return MediasageConfig(
        plex=PlexConfig(
            url=plex_url,
            token=plex_token,
            account_token=account_token,
            server_id=server_id,
            server_name=server_name,
            client_id=client_id,
            music_library=music_library,
        ),
        llm=LLM_SECTION_ADAPTER.validate_python(llm),
        budget=BudgetConfig(),
        defaults=DefaultsConfig(track_count=track_count),
    )


def connected_plex_mock(**attributes) -> MagicMock:
    """A Plex client that reports itself connected."""
    plex = MagicMock(**attributes)
    plex.connection.is_connected.return_value = True
    return plex


def serve_live_config(app) -> None:
    """Re-read the configuration dependency on every request.

    FastAPI binds `config_store.get` once, at import; a test that patches
    `ConfigStore.get` afterwards would not be seen by the bound method. This
    override looks the method up per call, so patching works as it reads.
    """
    app.dependency_overrides[config_store.get] = lambda: config_store.get()


@pytest.fixture
def client() -> TestClient:
    """A test client over a freshly built application.

    Built per test rather than shared: `create_app` mounts routes, and a test
    that changes what is mounted must not leak into the next one.
    """
    built = TestClient(create_app())
    serve_live_config(built.app)
    return built


@pytest.fixture(autouse=True)
def rebuilds(monkeypatch) -> SimpleNamespace:
    """Absorb the client a settings save builds.

    Patched at the constructor: that is what would open a connection, and
    autouse because no test may open one. Several tests assert on whether a
    rebuild happened at all.
    """
    plex = MagicMock()
    llm = MagicMock()
    monkeypatch.setattr(PlexClient, "of", plex)
    monkeypatch.setattr(LLMClient, "of", llm)
    return SimpleNamespace(plex=plex, llm=llm)


def serve_plex(app, monkeypatch, client: MagicMock | None) -> None:
    """Answer every Plex dependency from one client, or from none at all.

    None says nothing is configured, which is what a route that requires Plex
    must turn into a 503. The store itself holds it too: one route reaches for
    Plex only on the branch where the cache cannot answer.
    """
    connected = client is not None and client.connection.is_connected()

    def required():
        if not connected:
            raise PlexNotConnected("Plex not connected")
        return client

    monkeypatch.setattr(plex_store, "client", client)
    app.dependency_overrides.update(
        {
            plex_store.require: required,
            plex_store.get: lambda: client,
            plex_store.is_connected: lambda: connected,
        }
    )


@pytest.fixture
def plex(request, client, monkeypatch):
    """Resolve the Plex dependencies to `request.param`, or a connected client."""
    # `hasattr`, not a default: None is a meaningful parameter here -- it is
    # how a test says nothing is configured at all.
    served = request.param if hasattr(request, "param") else connected_plex_mock()

    serve_plex(client.app, monkeypatch, served)
    yield served
    client.app.dependency_overrides.clear()


@pytest.fixture
def answering():
    """Patch the provider probe to say the candidate settings work.

    Patched at the probe's own seam rather than at `probes.rejected`: a route
    that stopped probing must not still pass. Plex has no probe here -- it is
    proved by the sign-in, under `/api/plex`.
    """
    with patch("backend.api.probes.ModelListing.of", new_callable=AsyncMock) as listing:
        # Unsupported refuses no model name, whatever the test configured.
        listing.return_value = ModelListing(supported=False)
        yield
