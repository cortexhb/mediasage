"""Tests for connecting, classifying failures, and retrying bulk fetches."""

import os
from unittest.mock import MagicMock, patch

import pytest
from plexapi.exceptions import NotFound, Unauthorized
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout

from backend.plex import connection as connection_module
from backend.plex.connection import PlexConnection, PlexFetchError
from tests.plex.conftest import make_connection


def build(**server_behaviour) -> PlexConnection:
    """Connect against a patched `PlexServer` configured by keyword."""
    with patch.object(connection_module, "PlexServer", **server_behaviour):
        return PlexConnection(url="http://plex:32400", token="token", music_library="Music")


class TestPlexApiDefaults:
    """The plexapi settings that decide bulk-fetch request volume."""

    def test_autoreload_is_disabled(self):
        """Autoreload refetches every object with a missing attribute."""
        assert os.environ["PLEXAPI_PLEXAPI_AUTORELOAD"] == "false"

    def test_container_size_is_raised(self):
        """The default of 50 costs one round trip per 50 rows."""
        assert int(os.environ["PLEXAPI_PLEXAPI_CONTAINER_SIZE"]) >= 1000


class TestConnect:
    """What each kind of connection failure leaves behind."""

    def test_valid_credentials_connect(self):
        conn = build(return_value=MagicMock())
        assert (conn.is_connected(), conn.error) == (True, None)

    def test_blank_credentials_are_refused_without_dialling(self):
        conn = PlexConnection(url="", token="")
        assert conn.is_connected() is False
        assert conn.error is not None
        assert "required" in conn.error

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (Unauthorized("bad token"), "unauthorized"),
            (RequestsConnectionError("refused"), "cannot connect"),
            (Timeout("slow"), "timed out"),
            (RuntimeError("something else"), "plex connection error"),
        ],
    )
    def test_a_failure_is_reported_and_drops_both_handles(self, error, expected):
        conn = build(side_effect=error)
        assert conn.is_connected() is False
        assert conn.error is not None
        assert expected in conn.error.lower()
        assert conn.server is None

    def test_a_missing_library_keeps_the_server(self):
        """The setup wizard lists the libraries that do exist, so it needs one."""
        server = MagicMock()
        server.library.section.side_effect = NotFound("no such section")
        conn = build(return_value=server)

        assert conn.is_connected() is False
        assert conn.error is not None
        assert "not found" in conn.error
        assert conn.server is server
        assert conn.library is None


class TestReconnect:
    """A dropped connection is retried, but not on every call."""

    def test_a_disconnected_client_reconnects(self):
        conn = build(side_effect=RequestsConnectionError("down"))
        conn._last_attempt -= conn.reconnect_cooldown

        with patch.object(connection_module, "PlexServer", MagicMock()):
            assert conn.is_connected() is True

    def test_the_cooldown_is_respected(self):
        conn = build(side_effect=RequestsConnectionError("down"))

        with patch.object(connection_module, "PlexServer") as server:
            assert conn.is_connected() is False
            server.assert_not_called()

    def test_a_live_connection_does_not_redial(self):
        conn = build(return_value=MagicMock())

        with patch.object(connection_module, "PlexServer") as server:
            assert conn.is_connected() is True
            server.assert_not_called()


class TestTransientClassification:
    """Which failures are worth retrying."""

    @pytest.mark.parametrize(
        "error",
        [
            RequestsConnectionError("refused"),
            Timeout("slow"),
            RuntimeError("Plex server is overloaded"),
            RuntimeError("503 Service Unavailable"),
            RuntimeError("temporarily unavailable"),
        ],
    )
    def test_a_transient_failure_is_retried(self, error):
        assert PlexConnection.is_transient(error) is True

    @pytest.mark.parametrize(
        "error",
        [Unauthorized("bad token"), NotFound("gone"), ValueError("bad argument")],
    )
    def test_a_permanent_failure_is_not(self, error):
        assert PlexConnection.is_transient(error) is False


class TestWithRetries:
    """The retry loop every bulk fetch runs through."""

    def test_a_first_success_is_returned_untouched(self):
        assert make_connection().with_retries("label", lambda: "value") == "value"

    def test_it_retries_until_it_succeeds(self, no_sleep):
        attempts = []

        def flaky():
            attempts.append(1)
            if len(attempts) < 3:
                raise RequestsConnectionError("refused")
            return "value"

        assert make_connection().with_retries("label", flaky) == "value"
        assert len(attempts) == 3

    def test_the_backoff_grows(self, no_sleep, installed_config):
        def always_fails():
            raise RequestsConnectionError("refused")

        with pytest.raises(PlexFetchError):
            make_connection().with_retries("label", always_fails)

        assert no_sleep == installed_config.plex.retry_backoff

    def test_a_permanent_failure_is_not_retried(self, no_sleep):
        def unauthorized():
            raise Unauthorized("bad token")

        with pytest.raises(PlexFetchError):
            make_connection().with_retries("label", unauthorized)

        assert no_sleep == []

    def test_the_last_error_is_carried(self, no_sleep):
        def always_fails():
            raise RequestsConnectionError("refused")

        with pytest.raises(PlexFetchError, match="refused"):
            make_connection().with_retries("label", always_fails)


class TestServerFacts:
    """What the connection reports about the server it reached."""

    def test_the_machine_identifier_comes_from_the_server(self, connection, server):
        assert connection.machine_identifier() == "machine-1"

    def test_a_missing_server_has_no_identifier(self):
        assert make_connection().machine_identifier() is None

    def test_the_friendly_name_is_exposed(self, connection):
        assert connection.server_name == "My Plex Server"

    def test_only_music_sections_are_listed(self, connection, server):
        server.library.sections.return_value = [
            MagicMock(title="Music", type="artist"),
            MagicMock(title="Movies", type="movie"),
            MagicMock(title="Soundtracks", type="artist"),
        ]
        assert connection.music_libraries() == ["Music", "Soundtracks"]

    def test_a_failing_listing_is_empty_not_fatal(self, connection, server):
        server.library.sections.side_effect = RuntimeError("boom")
        assert connection.music_libraries() == []

    def test_the_playlist_url_names_the_server_and_playlist(self, connection):
        url = connection.playlist_url(42)
        assert "machine-1" in url
        assert url.endswith("%2Fplaylists%2F42")

    def test_without_a_server_there_is_no_playlist_url(self):
        assert make_connection().playlist_url(42) is None


class TestFetchItems:
    """Resolving rating keys, and surviving the ones that do not resolve."""

    def test_every_key_resolves(self, connection, server):
        server.fetchItem.side_effect = lambda key: f"item-{key}"
        fetched = connection.fetch_items(["1", "2"])

        assert fetched.items == ["item-1", "item-2"]
        assert (fetched.skipped, fetched.skipped_count) == ([], 0)
        assert bool(fetched) is True

    def test_an_unresolvable_key_is_collected_not_raised(self, connection, server):
        server.fetchItem.side_effect = [RuntimeError("gone"), "item-2"]
        fetched = connection.fetch_items(["1", "2"])

        assert (fetched.items, fetched.skipped) == (["item-2"], ["1"])

    def test_nothing_resolving_is_falsy(self, connection, server):
        server.fetchItem.side_effect = RuntimeError("gone")
        assert bool(connection.fetch_items(["1"])) is False
