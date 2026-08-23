"""Pytest fixtures for MediaSage tests."""

from unittest.mock import MagicMock

import pytest

from backend.config import MediasageConfig
from backend.config.store import config_store
from backend.models import Dimension, Track

# Every environment variable the config reads. A developer's shell may have
# these set, so tests must clear them or they assert against that machine
# instead of the values under test.
CONFIG_ENV_VARS = (
    "MEDIASAGE_DEFAULTS__TRACK_COUNT",
    "MEDIASAGE_LLM__API_KEY",
    "MEDIASAGE_LLM__CONTEXT_WINDOW",
    "MEDIASAGE_LLM__ENDPOINT_URL",
    "MEDIASAGE_LLM__MODEL_ANALYSIS",
    "MEDIASAGE_LLM__MODEL_GENERATION",
    "MEDIASAGE_LLM__PROVIDER",
    "MEDIASAGE_PLEX__MUSIC_LIBRARY",
    "MEDIASAGE_PLEX__TOKEN",
    "MEDIASAGE_PLEX__URL",
)


@pytest.fixture(autouse=True)
def installed_config(monkeypatch) -> MediasageConfig:
    """Install a complete configuration before every test.

    Tunables are read off the config at call time, so even a test that never
    mentions settings needs one installed; without it the developer's own
    config would be loaded and assertions would depend on their machine.
    """
    config = MediasageConfig(llm={"provider": "anthropic", "context_window": 200000})
    monkeypatch.setattr(config_store, "config", config)
    return config


@pytest.fixture
def tuned(monkeypatch, installed_config):
    """Reinstall the configuration with one section's fields overridden.

    Tunables are read straight off the store at their point of use, so a test
    that needs a different one changes the configuration rather than patching
    a reader that no longer exists.
    """

    def install(section: str, **overrides) -> MediasageConfig:
        current = config_store.get()
        config = current.model_copy(
            update={section: getattr(current, section).model_copy(update=overrides)}
        )
        monkeypatch.setattr(config_store, "config", config)
        return config

    return install


@pytest.fixture
def clean_config_env(monkeypatch):
    """Remove every config env var so a test sees only what it sets itself."""
    for var in CONFIG_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


@pytest.fixture
def temp_db(tmp_path):
    """A migrated database on a fresh file, with in-process sync state reset.

    Migrations build the schema, so tests exercise what the application
    actually ships rather than a parallel definition.
    """
    from backend.db import db, migrations
    from backend.library import library_sync
    from backend.library.models import SyncRun

    db.configure(f"sqlite:///{tmp_path / 'test.db'}")
    migrations.upgrade_to_head()
    library_sync._run = SyncRun()

    yield db

    db.dispose()


@pytest.fixture
def library_settings(monkeypatch):
    """Install a real configuration so library tunables are readable.

    Returns a callable that reinstalls the config with `LibraryConfig`
    overrides, for tests that need a different batch size or live rule.
    """
    from backend.config import LibraryConfig, MediasageConfig
    from backend.config.store import config_store

    def install(**overrides) -> LibraryConfig:
        config = MediasageConfig(
            llm={"provider": "anthropic", "context_window": 200000},
            library=LibraryConfig(**overrides),
        )
        monkeypatch.setattr(config_store, "config", config)
        return config.library

    install()
    return install


@pytest.fixture
def mock_plex_tracks() -> list[Track]:
    """Sample library tracks for testing filter/match logic."""
    return [
        Track(
            rating_key="1",
            title="Fake Plastic Trees",
            artist="Radiohead",
            album="The Bends",
            duration_ms=290000,
            year=1995,
            genres=["Alternative", "Rock"],
            art_url="/api/art/1",
        ),
        Track(
            rating_key="2",
            title="Black",
            artist="Pearl Jam",
            album="Ten",
            duration_ms=340000,
            year=1991,
            genres=["Grunge", "Rock"],
            art_url="/api/art/2",
        ),
        Track(
            rating_key="3",
            title="Creep",
            artist="Radiohead",
            album="Pablo Honey",
            duration_ms=238000,
            year=1993,
            genres=["Alternative", "Rock"],
            art_url="/api/art/3",
        ),
        Track(
            rating_key="4",
            title="Bitter Sweet Symphony",
            artist="The Verve",
            album="Urban Hymns",
            duration_ms=358000,
            year=1997,
            genres=["Alternative", "Britpop"],
            art_url="/api/art/4",
        ),
        Track(
            rating_key="5",
            title="Wonderwall",
            artist="Oasis",
            album="(What's the Story) Morning Glory?",
            duration_ms=259000,
            year=1995,
            genres=["Britpop", "Rock"],
            art_url="/api/art/5",
        ),
        Track(
            rating_key="6",
            title="Say It Ain't So",
            artist="Weezer",
            album="Weezer (Blue Album)",
            duration_ms=258000,
            year=1994,
            genres=["Alternative", "Rock"],
            art_url="/api/art/6",
        ),
        Track(
            rating_key="7",
            title="Under the Bridge",
            artist="Red Hot Chili Peppers",
            album="Blood Sugar Sex Magik",
            duration_ms=264000,
            year=1991,
            genres=["Alternative", "Rock", "Funk"],
            art_url="/api/art/7",
        ),
        Track(
            rating_key="8",
            title="Smells Like Teen Spirit",
            artist="Nirvana",
            album="Nevermind",
            duration_ms=301000,
            year=1991,
            genres=["Grunge", "Alternative", "Rock"],
            art_url="/api/art/8",
        ),
        Track(
            rating_key="9",
            title="Champagne Supernova - Live",
            artist="Oasis",
            album="Live at Knebworth 1996",
            duration_ms=460000,
            year=1996,
            genres=["Britpop", "Rock"],
            art_url="/api/art/9",
        ),
        Track(
            rating_key="10",
            title="Purple Rain",
            artist="Prince",
            album="Purple Rain",
            duration_ms=520000,
            year=1984,
            genres=["Pop", "Rock", "R&B"],
            art_url="/api/art/10",
        ),
    ]


@pytest.fixture
def mock_dimensions() -> list[Dimension]:
    """Sample dimensions for testing seed track analysis."""
    return [
        Dimension(
            id="mood",
            label="The melancholy, bittersweet mood",
            description="Emotionally heavy, reflective tone with a sense of yearning",
        ),
        Dimension(
            id="era",
            label="Mid-90s British alternative rock",
            description="The Britpop/post-grunge era sound",
        ),
        Dimension(
            id="instrumentation",
            label="Layered guitars with string arrangements",
            description="Electric and acoustic guitars with orchestral elements",
        ),
        Dimension(
            id="vocals",
            label="Vulnerable, falsetto-tinged vocals",
            description="Emotional delivery with moments of restraint",
        ),
        Dimension(
            id="theme",
            label="Alienation and modern disconnect",
            description="Themes of feeling out of place in consumer society",
        ),
    ]


@pytest.fixture
def mock_llm_response_tracks() -> list[dict]:
    """Sample LLM response for track selection."""
    return [
        {"artist": "Radiohead", "album": "The Bends", "title": "Fake Plastic Trees"},
        {"artist": "Pearl Jam", "album": "Ten", "title": "Black"},
        {"artist": "The Verve", "album": "Urban Hymns", "title": "Bitter Sweet Symphony"},
    ]


@pytest.fixture
def mock_llm_response_analysis() -> dict:
    """Sample LLM response for prompt analysis."""
    return {
        "genres": ["Alternative", "Rock"],
        "decades": ["1990s"],
        "reasoning": "The request for 'melancholy 90s alternative' suggests mid-90s alternative rock with emotionally introspective themes.",
    }


@pytest.fixture
def mock_plex_server(mocker):
    """Mock PlexServer for testing."""
    mock_server = MagicMock()
    mock_library = MagicMock()
    mock_server.library.section.return_value = mock_library
    return mock_server


@pytest.fixture
def mock_anthropic_client(mocker):
    """Mock Anthropic client for testing."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"test": "response"}')]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    mock_client.messages.create.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_openai_client(mocker):
    """Mock OpenAI client for testing."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content='{"test": "response"}'))]
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client
