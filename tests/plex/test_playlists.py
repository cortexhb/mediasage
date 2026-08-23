"""Tests for creating, listing and updating Plex playlists."""

from unittest.mock import MagicMock

from backend.plex.playlists import SCRATCH_SENTINEL, SCRATCH_TITLE, PlexPlaylists
from tests.plex.conftest import make_connection


def playlist_double(rating_key: int = 10, items: list[object] | None = None) -> MagicMock:
    """A Plex playlist holding `items`."""
    playlist = MagicMock()
    playlist.ratingKey = rating_key
    playlist.items.return_value = items or []
    return playlist


def listed(rating_key: int, title: str, *, smart: bool = False, radio: bool = False) -> MagicMock:
    """A playlist as `server.playlists()` returns it."""
    entry = MagicMock()
    entry.ratingKey = rating_key
    entry.title = title
    entry.leafCount = 3
    entry.smart = smart
    entry.radio = radio
    return entry


class TestCreate:
    """Creating a playlist from rating keys."""

    def test_it_reports_the_playlist_it_made(self, connection, server):
        server.fetchItem.side_effect = ["a", "b"]
        server.createPlaylist.return_value = playlist_double(10)

        result = PlexPlaylists(connection=connection).create("Mix", ["1", "2"])

        assert (result.success, result.playlist_id, result.tracks_added) == (True, "10", 2)
        assert result.playlist_url is not None
        assert "machine-1" in result.playlist_url

    def test_a_description_is_set_on_the_playlist(self, connection, server):
        playlist = playlist_double()
        server.createPlaylist.return_value = playlist

        PlexPlaylists(connection=connection).create("Mix", ["1"], "A summary")
        playlist.edit.assert_called_once_with(summary="A summary")

    def test_an_empty_description_is_not_written(self, connection, server):
        playlist = playlist_double()
        server.createPlaylist.return_value = playlist

        PlexPlaylists(connection=connection).create("Mix", ["1"], "")
        playlist.edit.assert_not_called()

    def test_a_failing_description_does_not_fail_the_playlist(self, connection, server):
        playlist = playlist_double()
        playlist.edit.side_effect = RuntimeError("rejected")
        server.createPlaylist.return_value = playlist

        assert PlexPlaylists(connection=connection).create("Mix", ["1"], "summary").success is True

    def test_unresolvable_keys_are_skipped_not_fatal(self, connection, server):
        server.fetchItem.side_effect = [RuntimeError("gone"), "b"]
        server.createPlaylist.return_value = playlist_double()

        result = PlexPlaylists(connection=connection).create("Mix", ["1", "2"])
        assert (result.tracks_added, result.tracks_skipped) == (1, 1)

    def test_nothing_resolving_is_an_error(self, connection, server):
        server.fetchItem.side_effect = RuntimeError("gone")
        result = PlexPlaylists(connection=connection).create("Mix", ["1"])

        assert (result.success, result.error) == (False, "No valid tracks found")
        server.createPlaylist.assert_not_called()

    def test_a_failing_creation_is_reported(self, connection, server):
        server.createPlaylist.side_effect = RuntimeError("refused")
        result = PlexPlaylists(connection=connection).create("Mix", ["1"])
        assert (result.success, result.error) == (False, "refused")

    def test_a_disconnected_server_is_reported(self):
        result = PlexPlaylists(connection=make_connection()).create("Mix", ["1"])
        assert (result.success, result.error) == (False, "Not connected to Plex")


class TestListing:
    """Which playlists the picker is offered."""

    def test_audio_playlists_are_listed_alphabetically(self, connection, server):
        server.playlists.return_value = [listed(2, "Zebra"), listed(1, "apple")]
        assert [p.title for p in PlexPlaylists(connection=connection).listing()] == ["apple", "Zebra"]

    def test_smart_and_radio_playlists_are_excluded(self, connection, server):
        """Their contents are a query, so added tracks would not stick."""
        server.playlists.return_value = [
            listed(1, "Plain"),
            listed(2, "Smart", smart=True),
            listed(3, "Radio", radio=True),
        ]
        assert [p.title for p in PlexPlaylists(connection=connection).listing()] == ["Plain"]

    def test_the_track_count_is_carried(self, connection, server):
        server.playlists.return_value = [listed(1, "Plain")]
        assert PlexPlaylists(connection=connection).listing()[0].track_count == 3

    def test_a_failing_call_is_empty_not_fatal(self, connection, server):
        server.playlists.side_effect = RuntimeError("boom")
        assert PlexPlaylists(connection=connection).listing() == []

    def test_a_disconnected_server_lists_nothing(self):
        assert PlexPlaylists(connection=make_connection()).listing() == []


class TestUpdateReplace:
    """Replacing a playlist's contents."""

    def test_new_tracks_are_added_before_old_ones_are_removed(self, connection, server):
        """A failed add must leave the old playlist intact."""
        old = [MagicMock()]
        playlist = playlist_double(10, old)
        order = []
        playlist.addItems.side_effect = lambda items: order.append("add")
        playlist.removeItems.side_effect = lambda items: order.append("remove")
        server.fetchItem.side_effect = [playlist, "new-1"]

        result = PlexPlaylists(connection=connection).update("10", ["1"], mode="replace")

        assert order == ["add", "remove"]
        assert (result.success, result.tracks_added) == (True, 1)

    def test_a_failed_removal_warns_about_duplicates(self, connection, server):
        playlist = playlist_double(10, [MagicMock()])
        playlist.removeItems.side_effect = RuntimeError("refused")
        server.fetchItem.side_effect = [playlist, "new-1"]

        result = PlexPlaylists(connection=connection).update("10", ["1"], mode="replace")

        assert result.success is True
        assert result.warning is not None
        assert "duplicates" in result.warning

    def test_nothing_resolving_leaves_the_playlist_alone(self, connection, server):
        playlist = playlist_double(10, [MagicMock()])
        server.fetchItem.side_effect = [playlist, RuntimeError("gone")]

        result = PlexPlaylists(connection=connection).update("10", ["1"], mode="replace")

        assert (result.success, result.tracks_skipped) == (False, 1)
        playlist.addItems.assert_not_called()
        playlist.removeItems.assert_not_called()

    def test_an_empty_playlist_is_not_asked_to_remove(self, connection, server):
        playlist = playlist_double(10, [])
        server.fetchItem.side_effect = [playlist, "new-1"]

        PlexPlaylists(connection=connection).update("10", ["1"], mode="replace")
        playlist.removeItems.assert_not_called()


class TestUpdateAppend:
    """Adding to a playlist without duplicating what it holds."""

    def test_tracks_already_present_are_counted_not_added(self, connection, server):
        existing = MagicMock()
        existing.ratingKey = 1
        playlist = playlist_double(10, [existing])
        server.fetchItem.side_effect = [playlist, "new-2"]

        result = PlexPlaylists(connection=connection).update("10", ["1", "2"], mode="append")

        assert (result.tracks_added, result.duplicates_skipped) == (1, 1)

    def test_an_all_duplicate_append_adds_nothing(self, connection, server):
        existing = MagicMock()
        existing.ratingKey = 1
        playlist = playlist_double(10, [existing])
        server.fetchItem.side_effect = [playlist]

        result = PlexPlaylists(connection=connection).update("10", ["1"], mode="append")

        assert (result.success, result.duplicates_skipped) == (True, 1)
        playlist.addItems.assert_not_called()

    def test_unresolvable_keys_are_skipped(self, connection, server):
        playlist = playlist_double(10, [])
        server.fetchItem.side_effect = [playlist, RuntimeError("gone"), "new-2"]

        result = PlexPlaylists(connection=connection).update("10", ["1", "2"], mode="append")
        assert (result.tracks_added, result.tracks_skipped) == (1, 1)


class TestUpdateScratch:
    """The scratch playlist is created on first use."""

    def test_it_is_created_when_absent(self, connection, server):
        server.playlists.return_value = []
        server.fetchItem.side_effect = ["a"]
        server.createPlaylist.return_value = playlist_double(20)

        result = PlexPlaylists(connection=connection).update(SCRATCH_SENTINEL, ["1"])

        assert result.success is True
        assert server.createPlaylist.call_args.args[0] == SCRATCH_TITLE

    def test_an_existing_one_is_reused(self, connection, server):
        existing = listed(20, SCRATCH_TITLE)
        server.playlists.return_value = [existing]
        playlist = playlist_double(20, [])
        server.fetchItem.side_effect = [playlist, "new-1"]

        result = PlexPlaylists(connection=connection).update(SCRATCH_SENTINEL, ["1"])

        assert result.success is True
        server.createPlaylist.assert_not_called()

    def test_a_failing_lookup_still_creates_one(self, connection, server):
        server.playlists.side_effect = RuntimeError("boom")
        server.fetchItem.side_effect = ["a"]
        server.createPlaylist.return_value = playlist_double(20)

        assert PlexPlaylists(connection=connection).update(SCRATCH_SENTINEL, ["1"]).success is True


class TestUpdateGuards:
    """What is refused before anything is touched."""

    def test_an_unknown_mode_is_refused(self, connection, server):
        result = PlexPlaylists(connection=connection).update("10", ["1"], mode="sideways")

        assert (result.success, result.error) == (False, "Unknown update mode: sideways")
        server.fetchItem.assert_not_called()

    def test_an_unknown_mode_does_not_create_the_scratch_playlist(self, connection, server):
        PlexPlaylists(connection=connection).update(SCRATCH_SENTINEL, ["1"], mode="sideways")
        server.createPlaylist.assert_not_called()

    def test_a_disconnected_server_is_reported(self):
        result = PlexPlaylists(connection=make_connection()).update("10", ["1"])
        assert (result.success, result.error) == (False, "Not connected to Plex")

    def test_a_failure_mid_update_is_reported(self, connection, server):
        server.fetchItem.side_effect = RuntimeError("gone")
        result = PlexPlaylists(connection=connection).update("10", ["1"])
        assert (result.success, result.error) == (False, "gone")
