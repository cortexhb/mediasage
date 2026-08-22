"""Tests for the facade and the store that holds it."""

from unittest.mock import MagicMock, patch

from backend.config import PlexConfig
from backend.plex import connection as connection_module
from backend.plex.client import PlexClient, PlexClientStore


def build(config: PlexConfig, server: MagicMock | None = None) -> PlexClient:
    """A client whose connection dialled a patched `PlexServer`."""
    with patch.object(connection_module, "PlexServer", return_value=server or MagicMock()):
        return PlexClient.of(config)


class TestOf:
    """Building a client from the Plex configuration section."""

    def test_the_configuration_reaches_the_connection(self):
        config = PlexConfig(url="http://plex:32400", token="token", music_library="Tunes")
        client = build(config)

        assert client.connection.url == "http://plex:32400"
        assert client.connection.music_library == "Tunes"

    def test_it_connects_immediately(self):
        client = build(PlexConfig(url="http://plex:32400", token="token"))
        assert client.is_connected() is True

    def test_a_bad_configuration_is_visible_without_a_call(self):
        client = PlexClient.of(PlexConfig(url="", token=""))
        assert client.is_connected() is False
        assert "required" in client.error


class TestDelegation:
    """The facade forwards; it does not reimplement."""

    def test_a_library_read_reaches_the_section(self):
        server = MagicMock()
        client = build(PlexConfig(url="http://plex:32400", token="token"), server)
        section = server.library.section.return_value
        section.totalViewSize.return_value = 4200

        assert client.total_tracks() == 4200

    def test_a_playlist_read_reaches_the_server(self):
        server = MagicMock()
        server.playlists.return_value = []
        client = build(PlexConfig(url="http://plex:32400", token="token"), server)

        assert client.playlists() == []
        server.playlists.assert_called_once_with(playlistType="audio")

    def test_the_server_name_is_forwarded(self):
        server = MagicMock()
        server.friendlyName = "My Plex Server"
        client = build(PlexConfig(url="http://plex:32400", token="token"), server)

        assert client.server_name == "My Plex Server"


class TestStore:
    """The single client the application talks through."""

    def test_it_starts_empty(self):
        assert PlexClientStore().get() is None

    def test_init_installs_a_client(self):
        store = PlexClientStore()
        with patch.object(connection_module, "PlexServer", MagicMock()):
            client = store.init(PlexConfig(url="http://plex:32400", token="token"))

        assert store.get() is client

    def test_init_replaces_the_previous_client(self):
        store = PlexClientStore()
        with patch.object(connection_module, "PlexServer", MagicMock()):
            first = store.init(PlexConfig(url="http://one:32400", token="token"))
            second = store.init(PlexConfig(url="http://two:32400", token="token"))

        assert store.get() is second
        assert first is not second
