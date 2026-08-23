"""Tests for the composed client and the store that holds it."""

from unittest.mock import MagicMock, patch

import pytest

from backend.config import PlexConfig
from backend.plex import connection as connection_module
from backend.plex.client import PlexClient, PlexClientStore, PlexNotConnected


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
        assert client.connection.is_connected() is True

    def test_a_bad_configuration_is_visible_without_a_call(self):
        client = PlexClient.of(PlexConfig(url="", token=""))
        assert client.connection.is_connected() is False
        assert client.connection.error is not None
        assert "required" in client.connection.error


class TestComposition:
    """All three sit over the one connection, and are built only once."""

    def test_a_library_read_reaches_the_section(self):
        server = MagicMock()
        client = build(PlexConfig(url="http://plex:32400", token="token"), server)
        section = server.library.section.return_value
        section.totalViewSize.return_value = 4200

        assert client.library.total_tracks() == 4200

    def test_a_playlist_read_reaches_the_server(self):
        server = MagicMock()
        server.playlists.return_value = []
        client = build(PlexConfig(url="http://plex:32400", token="token"), server)

        assert client.playlists.listing() == []
        server.playlists.assert_called_once_with(playlistType="audio")

    def test_each_one_sits_over_the_client_connection(self):
        """A second connection would give the client two servers."""
        client = build(PlexConfig(url="http://plex:32400", token="token"))

        for over in (client.library, client.playlists, client.playback):
            assert over.connection is client.connection

    def test_they_are_built_once(self):
        """A fresh model per access would revalidate the connection per call."""
        client = build(PlexConfig(url="http://plex:32400", token="token"))

        assert client.library is client.library


class TestStore:
    """The single client the application talks through."""

    def test_it_starts_empty(self):
        assert PlexClientStore().get() is None

    def test_the_held_client_is_the_one_handed_back(self):
        """`require` must not hand back a copy of what was installed."""
        store = PlexClientStore()
        with patch.object(connection_module, "PlexServer", MagicMock()):
            store.client = PlexClient.of(PlexConfig(url="http://plex:32400", token="token"))

        assert store.get() is store.client

    def test_an_unconnected_client_is_not_handed_out(self):
        """A client that exists but cannot reach its server is not usable."""
        store = PlexClientStore()
        store.client = MagicMock()
        store.client.connection.is_connected.return_value = False

        assert store.is_connected() is False
        with pytest.raises(PlexNotConnected):
            store.require()
