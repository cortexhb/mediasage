"""Fixtures for the plex package: a stand-in server and library section."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.plex import connection as connection_module
from backend.plex.connection import PlexConnection


def raw_track(
    rating_key: str = "1",
    title: str = "Song",
    *,
    artist: str = "Artist",
    album: str = "Album",
    year: int | None = 1994,
    thumb: str | None = "/library/metadata/1/thumb/1",
) -> SimpleNamespace:
    """A stand-in for a plexapi track, carrying only what the reads touch."""
    return SimpleNamespace(
        ratingKey=rating_key,
        title=title,
        grandparentTitle=artist,
        parentTitle=album,
        parentYear=year,
        duration=180000,
        genres=[SimpleNamespace(tag="Rock")],
        thumb=thumb,
        parentThumb=None,
        grandparentThumb=None,
    )


def choice(title: str) -> SimpleNamespace:
    """A stand-in for one of Plex's filter choices."""
    return SimpleNamespace(title=title)


def make_connection(server: object | None = None, library: object | None = None) -> PlexConnection:
    """A connection with its handles injected rather than dialled.

    `PlexConnection` connects in `model_post_init`, so the constructor is run
    against a patched `PlexServer` and the handles are then replaced.
    """
    with patch.object(connection_module, "PlexServer", MagicMock()):
        conn = PlexConnection(url="http://plex:32400", token="token")
    conn._server = server
    conn._library = library
    conn._error = None
    return conn


@pytest.fixture
def section() -> MagicMock:
    """A music library section."""
    return MagicMock()


@pytest.fixture
def server() -> MagicMock:
    """A Plex server with a stable machine identifier."""
    plex_server = MagicMock()
    plex_server.machineIdentifier = "machine-1"
    plex_server.friendlyName = "My Plex Server"
    return plex_server


@pytest.fixture
def connection(server, section) -> PlexConnection:
    """A connected handle over the `server` and `section` doubles."""
    return make_connection(server, section)


@pytest.fixture
def no_sleep(monkeypatch) -> list[float]:
    """Record retry delays instead of waiting them out."""
    delays: list[float] = []
    monkeypatch.setattr(connection_module.time, "sleep", delays.append)
    return delays
