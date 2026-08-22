"""Tests for discovering players and sending them a queue."""

from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError

from backend.plex import playback
from tests.plex.conftest import make_connection


def local_client(
    client_id: str = "client-1",
    *,
    title: str = "Living Room",
    product: str = "Plex for Mac",
    platform: str = "macOS",
    capabilities: object = "playback,navigation",
    playing: bool = False,
) -> MagicMock:
    """A GDM-discovered player."""
    client = MagicMock()
    client.machineIdentifier = client_id
    client.title = title
    client.product = product
    client.platform = platform
    client.protocolCapabilities = capabilities
    client.isPlayingMedia.return_value = playing
    return client


def resource(
    client_id: str = "cloud-1",
    *,
    name: str = "Phone",
    product: str = "Plexamp",
    platform: str = "iOS",
    provides: str = "player",
    presence: bool = True,
) -> MagicMock:
    """A cloud-connected player from the account's resources."""
    entry = MagicMock()
    entry.clientIdentifier = client_id
    entry.name = name
    entry.product = product
    entry.platform = platform
    entry.provides = provides
    entry.presence = presence
    return entry


def only_local(server: MagicMock, clients: list[MagicMock]) -> None:
    """Serve `clients` locally and nothing from the account."""
    server.clients.return_value = clients
    server.myPlexAccount.return_value.resources.return_value = []
    server.sessions.return_value = []


class TestIsMobile:
    """Which players need an active session before accepting a queue."""

    @pytest.mark.parametrize(
        ("product", "platform"),
        [("Plexamp", "iOS"), ("Plex", "Android"), ("Plex", "tvOS"), ("Plex for iPad", "unknown")],
    )
    def test_a_mobile_or_tv_player_is_marked(self, product, platform):
        assert playback.is_mobile(product, platform) is True

    @pytest.mark.parametrize(
        ("product", "platform"), [("Plex for Mac", "macOS"), ("Plex Web", "Chrome")]
    )
    def test_a_desktop_player_is_not(self, product, platform):
        assert playback.is_mobile(product, platform) is False


class TestClients:
    """Discovery across both routes."""

    def test_a_playback_capable_local_client_is_listed(self, connection, server):
        only_local(server, [local_client()])
        found = playback.clients(connection)

        assert [client.client_id for client in found] == ["client-1"]
        assert found[0].name == "Living Room"

    def test_a_client_without_playback_is_excluded(self, connection, server):
        only_local(server, [local_client(capabilities="navigation")])
        assert playback.clients(connection) == []

    def test_capabilities_may_arrive_as_a_list(self, connection, server):
        only_local(server, [local_client(capabilities=["playback"])])
        assert len(playback.clients(connection)) == 1

    def test_an_unresponsive_client_is_dropped(self, connection, server):
        """Offering it in the picker would only fail later."""
        broken = local_client()
        broken.isPlayingMedia.side_effect = RuntimeError("no answer")
        only_local(server, [broken])
        assert playback.clients(connection) == []

    def test_the_playing_state_is_carried(self, connection, server):
        only_local(server, [local_client(playing=True)])
        assert playback.clients(connection)[0].is_playing is True

    def test_a_failing_local_discovery_still_returns_cloud_players(self, connection, server):
        server.clients.side_effect = RuntimeError("gdm down")
        server.myPlexAccount.return_value.resources.return_value = [resource()]
        server.sessions.return_value = []

        assert [client.client_id for client in playback.clients(connection)] == ["cloud-1"]

    def test_a_cloud_player_is_listed(self, connection, server):
        server.clients.return_value = []
        server.myPlexAccount.return_value.resources.return_value = [resource()]
        server.sessions.return_value = []

        found = playback.clients(connection)
        assert (found[0].name, found[0].is_mobile) == ("Phone", True)

    def test_a_non_player_resource_is_excluded(self, connection, server):
        server.clients.return_value = []
        server.myPlexAccount.return_value.resources.return_value = [resource(provides="server")]
        server.sessions.return_value = []

        assert playback.clients(connection) == []

    def test_an_offline_resource_is_excluded(self, connection, server):
        server.clients.return_value = []
        server.myPlexAccount.return_value.resources.return_value = [resource(presence=False)]
        server.sessions.return_value = []

        assert playback.clients(connection) == []

    def test_a_locally_discovered_player_is_not_listed_twice(self, connection, server):
        server.clients.return_value = [local_client("shared")]
        server.myPlexAccount.return_value.resources.return_value = [resource("shared")]
        server.sessions.return_value = []

        assert len(playback.clients(connection)) == 1

    def test_a_cloud_player_playing_is_read_from_the_sessions(self, connection, server):
        server.clients.return_value = []
        server.myPlexAccount.return_value.resources.return_value = [resource("cloud-1")]
        session = MagicMock()
        session.player.machineIdentifier = "cloud-1"
        server.sessions.return_value = [session]

        assert playback.clients(connection)[0].is_playing is True

    def test_a_failing_account_query_still_returns_local_players(self, connection, server):
        server.clients.return_value = [local_client()]
        server.myPlexAccount.side_effect = RuntimeError("offline")

        assert len(playback.clients(connection)) == 1

    def test_a_disconnected_server_finds_nothing(self):
        assert playback.clients(make_connection()) == []


class TestPlayQueueReplace:
    """Starting a new queue on a player."""

    def test_it_creates_a_queue_and_plays_it(self, connection, server):
        client = local_client()
        server.clients.return_value = [client]
        server.fetchItem.side_effect = ["a", "b"]

        with patch.object(playback, "PlayQueue") as queue:
            result = playback.play_queue(connection, ["1", "2"], "client-1")

        assert (result.success, result.tracks_queued) == (True, 2)
        assert result.client_name == "Living Room"
        client.playMedia.assert_called_once_with(queue.create.return_value)

    def test_the_queue_starts_on_the_first_track(self, connection, server):
        server.clients.return_value = [local_client()]
        server.fetchItem.side_effect = ["a", "b"]

        with patch.object(playback, "PlayQueue") as queue:
            playback.play_queue(connection, ["1", "2"], "client-1")

        assert queue.create.call_args.kwargs["startItem"] == "a"

    def test_unresolvable_keys_are_reported(self, connection, server):
        server.clients.return_value = [local_client()]
        server.fetchItem.side_effect = [RuntimeError("gone"), "b"]

        with patch.object(playback, "PlayQueue"):
            result = playback.play_queue(connection, ["1", "2"], "client-1")

        assert (result.tracks_queued, result.tracks_skipped) == (1, 1)

    def test_a_client_going_offline_is_reported(self, connection, server):
        client = local_client()
        client.playMedia.side_effect = RequestsConnectionError("gone")
        server.clients.return_value = [client]
        server.fetchItem.side_effect = ["a"]

        with patch.object(playback, "PlayQueue"):
            result = playback.play_queue(connection, ["1"], "client-1")

        assert result.success is False
        assert "went offline" in result.error


class TestPlayQueueNext:
    """Inserting after the currently playing track."""

    def timeline(self, queue_id: int | None = 99, entry_type: str = "music") -> MagicMock:
        entry = MagicMock()
        entry.type = entry_type
        entry.playQueueID = queue_id
        return entry

    def test_tracks_are_inserted_in_reverse_so_they_play_in_order(self, connection, server):
        client = local_client()
        client.timelines.return_value = [self.timeline()]
        server.clients.return_value = [client]
        server.fetchItem.side_effect = ["a", "b"]

        with patch.object(playback, "PlayQueue") as queue:
            existing = queue.get.return_value
            result = playback.play_queue(connection, ["1", "2"], "client-1", mode="play_next")

        added = [call.args[0] for call in existing.addItem.call_args_list]
        assert added == ["b", "a"]
        assert result.tracks_queued == 2

    def test_only_the_last_insert_refreshes_the_client(self, connection, server):
        client = local_client()
        client.timelines.return_value = [self.timeline()]
        server.clients.return_value = [client]
        server.fetchItem.side_effect = ["a", "b"]

        with patch.object(playback, "PlayQueue") as queue:
            existing = queue.get.return_value
            playback.play_queue(connection, ["1", "2"], "client-1", mode="play_next")

        refreshes = [call.kwargs["refresh"] for call in existing.addItem.call_args_list]
        assert refreshes == [False, True]

    def test_a_client_with_no_music_queue_is_refused(self, connection, server):
        client = local_client()
        client.timelines.return_value = [self.timeline(entry_type="video")]
        server.clients.return_value = [client]
        server.fetchItem.side_effect = ["a"]

        with patch.object(playback, "PlayQueue"):
            result = playback.play_queue(connection, ["1"], "client-1", mode="play_next")

        assert (result.success, result.error) == (False, "No active play queue on this client")

    def test_an_unreadable_timeline_is_reported(self, connection, server):
        client = local_client()
        client.timelines.side_effect = RuntimeError("no answer")
        server.clients.return_value = [client]
        server.fetchItem.side_effect = ["a"]

        with patch.object(playback, "PlayQueue"):
            result = playback.play_queue(connection, ["1"], "client-1", mode="play_next")

        assert result.error == "Could not read active queue from client"

    def test_every_insert_failing_is_not_reported_as_success(self, connection, server):
        client = local_client()
        client.timelines.return_value = [self.timeline()]
        server.clients.return_value = [client]
        server.fetchItem.side_effect = [MagicMock(ratingKey=1)]

        with patch.object(playback, "PlayQueue") as queue:
            queue.get.return_value.addItem.side_effect = RuntimeError("refused")
            result = playback.play_queue(connection, ["1"], "client-1", mode="play_next")

        assert (result.success, result.tracks_queued) == (False, 0)

    def test_one_failing_insert_still_queues_the_rest(self, connection, server):
        client = local_client()
        client.timelines.return_value = [self.timeline()]
        server.clients.return_value = [client]
        server.fetchItem.side_effect = [MagicMock(ratingKey=1), MagicMock(ratingKey=2)]

        with patch.object(playback, "PlayQueue") as queue:
            queue.get.return_value.addItem.side_effect = [RuntimeError("refused"), None]
            result = playback.play_queue(connection, ["1", "2"], "client-1", mode="play_next")

        assert (result.success, result.tracks_queued) == (True, 1)


class TestPlayQueueGuards:
    """What is refused before a queue is built."""

    def test_an_unreachable_client_is_a_not_found(self, connection, server):
        server.clients.return_value = []
        server.myPlexAccount.return_value.resources.return_value = []

        result = playback.play_queue(connection, ["1"], "missing")

        assert (result.success, result.error_code) == (False, "not_found")

    def test_a_cloud_client_is_connected_to(self, connection, server):
        server.clients.return_value = []
        entry = resource("cloud-1")
        entry.connect.return_value = local_client("cloud-1", title="Phone")
        server.myPlexAccount.return_value.resources.return_value = [entry]
        server.fetchItem.side_effect = ["a"]

        with patch.object(playback, "PlayQueue"):
            result = playback.play_queue(connection, ["1"], "cloud-1")

        assert (result.success, result.client_name) == (True, "Phone")

    def test_nothing_resolving_is_refused(self, connection, server):
        server.clients.return_value = [local_client()]
        server.fetchItem.side_effect = RuntimeError("gone")

        result = playback.play_queue(connection, ["1"], "client-1")
        assert (result.success, result.error) == (False, "No valid tracks found")

    def test_an_unknown_mode_is_refused(self, connection, server):
        result = playback.play_queue(connection, ["1"], "client-1", mode="sideways")

        assert (result.success, result.error) == (False, "Unknown play queue mode: sideways")
        server.clients.assert_not_called()

    def test_a_disconnected_server_is_reported(self):
        result = playback.play_queue(make_connection(), ["1"], "client-1")
        assert (result.success, result.error) == (False, "Not connected to Plex")

    def test_commands_are_proxied_through_the_server(self, connection, server):
        client = local_client()
        server.clients.return_value = [client]
        server.fetchItem.side_effect = ["a"]

        with patch.object(playback, "PlayQueue"):
            playback.play_queue(connection, ["1"], "client-1")

        client.proxyThroughServer.assert_called_once_with(value=True)

    def test_a_client_that_cannot_be_proxied_still_plays(self, connection, server):
        client = local_client()
        client.proxyThroughServer.side_effect = RuntimeError("unsupported")
        server.clients.return_value = [client]
        server.fetchItem.side_effect = ["a"]

        with patch.object(playback, "PlayQueue"):
            assert playback.play_queue(connection, ["1"], "client-1").success is True
