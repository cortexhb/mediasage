"""Tests for the sync, the only writer of tracks and their genre rows."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select

from backend.db import db
from backend.library import library_sync
from backend.library.models import AlbumMetadata
from backend.library.tables import SyncState, Track, TrackGenre

from .conftest import FakePlexClient, plex_track


def cached_tracks() -> dict[str, Track]:
    with db.session() as session:
        return {track.rating_key: track for track in session.scalars(select(Track)).all()}


def cached_genres() -> list[tuple[str, str]]:
    with db.session() as session:
        return sorted(
            (row.rating_key, row.genre_lower) for row in session.scalars(select(TrackGenre)).all()
        )


@pytest.fixture
def plex(library_settings) -> FakePlexClient:
    """Three tracks across two albums, on a server that answers."""
    return FakePlexClient(
        tracks=[
            plex_track("1", "Song One", artist="Artist A", album="Album X", parent_key="100"),
            plex_track("2", "Song Two", artist="Artist B", album="Album Y", parent_key="101"),
            plex_track("3", "Song Three", artist="Artist A", album="Album X", parent_key="100"),
        ],
        albums={
            "100": AlbumMetadata(genres=["Rock", "Alternative"], year=1995),
            "101": AlbumMetadata(genres=["Electronic"], year=2020),
        },
    )


class TestSuccessfulSync:
    """The happy path, and what it writes."""

    def test_it_reports_success_and_a_count(self, temp_db, plex):
        result = library_sync.run(plex)
        assert (result.success, result.track_count) == (True, 3)

    def test_every_track_is_written(self, temp_db, plex):
        library_sync.run(plex)
        assert len(cached_tracks()) == 3

    def test_genres_come_from_the_album(self, temp_db, plex):
        library_sync.run(plex)
        assert cached_tracks()["1"].genres == ["Rock", "Alternative"]

    def test_the_year_comes_from_the_album(self, temp_db, plex):
        library_sync.run(plex)
        assert cached_tracks()["2"].year == 2020

    def test_an_album_without_metadata_is_not_fatal(self, temp_db, library_settings):
        library_sync.run(FakePlexClient(tracks=[plex_track("1", parent_key="missing")], albums={}))
        assert cached_tracks()["1"].genres == []

    def test_sync_state_records_the_run(self, temp_db, plex):
        library_sync.run(plex)
        state = library_sync.status()
        assert (state.track_count, state.plex_server_id) == (3, "test-server")
        assert state.synced_at is not None

    def test_the_checkpoint_is_cleared_on_success(self, temp_db, plex):
        library_sync.run(plex)
        with db.session() as session:
            state = SyncState.load(session)
            assert (state.sync_token, state.sync_cursor) == (None, 0)


class TestGenreIndex:
    """What the dropped triggers used to guarantee."""

    def test_a_genre_row_is_written_per_track_genre(self, temp_db, plex):
        library_sync.run(plex)
        assert cached_genres() == [
            ("1", "alternative"),
            ("1", "rock"),
            ("2", "electronic"),
            ("3", "alternative"),
            ("3", "rock"),
        ]

    def test_case_variants_do_not_collide(self, temp_db, library_settings):
        client = FakePlexClient(albums={"100": AlbumMetadata(genres=["Rock", "rock"], year=1994)})
        library_sync.run(client)
        assert cached_genres() == [("1", "rock")]

    def test_a_re_sync_replaces_stale_genre_rows(self, temp_db, library_settings):
        library_sync.run(FakePlexClient(albums={"100": AlbumMetadata(genres=["Rock"], year=1994)}))
        library_sync.run(FakePlexClient(albums={"100": AlbumMetadata(genres=["Jazz"], year=1994)}))
        assert cached_genres() == [("1", "jazz")]

    def test_non_string_genres_are_dropped(self, temp_db, library_settings):
        client = FakePlexClient(albums={"100": AlbumMetadata(genres=["Rock", 7, None], year=1994)})
        library_sync.run(client)
        assert cached_genres() == [("1", "rock")]


class TestLiveDetection:
    """The configured rule is applied while rows are built."""

    def test_a_live_title_is_marked(self, temp_db, library_settings):
        library_sync.run(FakePlexClient(tracks=[plex_track("1", "Song (Live)")]))
        assert cached_tracks()["1"].is_live is True

    def test_a_studio_title_is_not(self, temp_db, library_settings):
        library_sync.run(FakePlexClient(tracks=[plex_track("1", "Song")]))
        assert cached_tracks()["1"].is_live is False

    def test_the_rule_follows_the_configuration(self, temp_db, library_settings):
        library_settings(live_keywords=[], dated_titles_are_live=False)
        library_sync.run(FakePlexClient(tracks=[plex_track("1", "Song (Live)")]))
        assert cached_tracks()["1"].is_live is False


class TestSweep:
    """Rows the completed sync did not write are removed, but only then."""

    def test_tracks_gone_from_plex_are_removed(self, temp_db, library_settings, seed_tracks):
        seed_tracks(
            {"rating_key": "stale", "title": "T", "artist": "A", "album": "B", "genres": ["Rock"]}
        )
        library_sync.run(FakePlexClient())
        assert set(cached_tracks()) == {"1"}

    def test_their_genre_rows_go_with_them(self, temp_db, library_settings, seed_tracks):
        seed_tracks(
            {"rating_key": "stale", "title": "T", "artist": "A", "album": "B", "genres": ["Polka"]}
        )
        library_sync.run(FakePlexClient())
        assert all(key != "stale" for key, _ in cached_genres())


class TestFailure:
    """A failed sync keeps the cache usable and says it can be retried."""

    def test_a_missing_server_id_is_refused(self, temp_db, library_settings):
        client = FakePlexClient()
        client.server_id = None
        result = library_sync.run(client)
        assert result.success is False
        assert result.error is not None
        assert "server identifier" in result.error.lower()

    def test_a_failure_is_marked_resumable(self, temp_db, library_settings):
        class Failing(FakePlexClient):
            def album_metadata(self, on_progress=None):
                raise ConnectionError("Plex unreachable")

        result = library_sync.run(Failing())
        assert (result.success, result.resumable) == (False, True)

    def test_previously_cached_tracks_survive(self, temp_db, plex):
        library_sync.run(plex)

        class Failing(FakePlexClient):
            def album_metadata(self, on_progress=None):
                raise ConnectionError("Plex unreachable")

        library_sync.run(Failing())
        assert library_sync.has_tracks() is True
        assert library_sync.status().track_count == 3

    def test_the_error_is_visible_then_cleared_by_a_good_run(self, temp_db, plex):
        class Failing(FakePlexClient):
            def album_metadata(self, on_progress=None):
                raise ConnectionError("Plex unreachable")

        library_sync.run(Failing())
        assert library_sync.status().error == "Plex unreachable"

        library_sync.run(plex)
        assert library_sync.status().error is None


class TestResume:
    """A checkpoint means the next attempt continues instead of refetching."""

    @pytest.fixture
    def dying_client(self, library_settings):
        library_settings(sync_batch_size=2)

        class Dying(FakePlexClient):
            def iter_raw_tracks(self, start=0, page_size=1000):
                self.starts.append(start)
                yield self.tracks[start : start + 2]
                raise ConnectionError("Plex died mid-sync")

        return Dying(tracks=[plex_track(str(i)) for i in range(6)])

    def test_the_checkpoint_records_what_was_written(self, temp_db, dying_client):
        library_sync.run(dying_client)
        with db.session() as session:
            state = SyncState.load(session)
        assert state.sync_token is not None
        assert state.sync_cursor == 2

    def test_the_checkpoint_never_claims_unwritten_rows(self, temp_db, dying_client):
        library_sync.run(dying_client)
        with db.session() as session:
            cursor = SyncState.load(session).sync_cursor
        assert len(cached_tracks()) == cursor

    def test_the_next_run_starts_from_the_checkpoint(self, temp_db, dying_client):
        library_sync.run(dying_client)

        resuming = FakePlexClient(tracks=dying_client.tracks)
        result = library_sync.run(resuming)

        assert resuming.starts == [2]
        assert result.track_count == 6

    def test_a_completed_sync_starts_from_zero(self, temp_db, plex):
        library_sync.run(plex)
        again = FakePlexClient(tracks=plex.tracks, albums=plex.albums)
        library_sync.run(again)
        assert again.starts == [0]


class TestConcurrency:
    """One sync at a time, since two would fight over the same checkpoint."""

    def test_a_second_sync_is_refused(self, temp_db, plex):
        library_sync._run.is_syncing = True
        result = library_sync.run(plex)
        assert result.success is False
        assert result.error is not None
        assert "already in progress" in result.error

    def test_the_claim_is_released_after_a_failure(self, temp_db, library_settings):
        class Failing(FakePlexClient):
            def album_metadata(self, on_progress=None):
                raise ConnectionError("boom")

        library_sync.run(Failing())
        assert library_sync.snapshot().is_syncing is False

    def test_progress_is_empty_once_the_run_ends(self, temp_db, plex):
        library_sync.run(plex)
        assert library_sync.snapshot().progress.current == 0


class TestProgress:
    """Progress is reported per batch, for the UI to poll."""

    def test_the_callback_fires_once_per_batch(self, temp_db, library_settings):
        library_settings(sync_batch_size=2)
        seen: list[tuple[int, int]] = []
        library_sync.run(
            FakePlexClient(tracks=[plex_track(str(i)) for i in range(4)]),
            on_progress=lambda current, total: seen.append((current, total)),
        )
        assert seen == [(2, 4), (4, 4)]

    def test_a_library_smaller_than_a_batch_reports_nothing(self, temp_db, plex):
        seen: list[tuple[int, int]] = []
        library_sync.run(plex, on_progress=lambda current, total: seen.append((current, total)))
        assert seen == []


class TestAlbumPhases:
    """The album stages report progress, so the UI can draw a moving bar.

    Before this they set no `current` at all: `_advance(total=...)` recorded
    the track count and nothing moved until the processing phase, which on a
    large library is minutes of a bar that cannot budge.
    """

    def phases(self, plex) -> list[tuple[str | None, int, int]]:
        """Every phase the sync passed through, in order, with its counts."""
        seen: list[tuple[str | None, int, int]] = []
        original = library_sync._advance

        def record(**fields):
            original(**fields)
            run = library_sync.snapshot().progress
            seen.append((run.phase, run.current, run.total))

        with patch.object(library_sync, "_advance", record):
            library_sync.run(plex)
        return seen

    def test_the_album_stage_reports_against_the_album_count(self, temp_db, plex):
        assert ("fetching_albums", 2, 2) in self.phases(plex)

    def test_the_genre_stage_reports_separately(self, temp_db, plex):
        # Its own phase because it counts genre choices, not albums.
        assert ("fetching_genres", 1, 1) in self.phases(plex)

    def test_processing_restores_the_track_total(self, temp_db, plex):
        # Otherwise the bar would keep measuring against the album count.
        assert ("processing", 0, 3) in self.phases(plex)

    def test_the_stages_run_in_order(self, temp_db, plex):
        order = [phase for phase, _current, _total in self.phases(plex)]
        assert order.index("fetching_albums") < order.index("fetching_genres")
        assert order.index("fetching_genres") < order.index("processing")


class TestServerChange:
    """A different Plex server means the cache describes the wrong library."""

    def test_no_change_before_the_first_sync(self, temp_db):
        assert library_sync.server_changed("anything") is False

    def test_the_same_server_is_not_a_change(self, temp_db, plex):
        library_sync.run(plex)
        assert library_sync.server_changed("test-server") is False

    def test_a_different_server_is(self, temp_db, plex):
        library_sync.run(plex)
        assert library_sync.server_changed("other") is True

    def test_syncing_a_new_server_clears_the_old_cache(self, temp_db, plex):
        library_sync.run(plex)

        replacement = FakePlexClient(tracks=[plex_track("99")])
        replacement.server_id = "other-server"
        library_sync.run(replacement)

        assert set(cached_tracks()) == {"99"}


class TestCacheState:
    """What the rest of the app asks about the cache."""

    def test_an_empty_cache_has_no_tracks(self, temp_db):
        assert library_sync.has_tracks() is False

    def test_a_synced_cache_has_tracks(self, temp_db, plex):
        library_sync.run(plex)
        assert library_sync.has_tracks() is True

    def test_clearing_removes_tracks_and_their_genres(self, temp_db, plex):
        library_sync.run(plex)
        library_sync.clear_cache()
        assert (cached_tracks(), cached_genres()) == ({}, [])

    def test_clearing_forgets_the_last_sync(self, temp_db, plex):
        library_sync.run(plex)
        library_sync.clear_cache()
        state = library_sync.status()
        assert (state.track_count, state.synced_at) == (0, None)


class TestStaleness:
    """Age is measured against the recorded sync time."""

    def test_a_cache_that_never_synced_is_stale(self, temp_db, library_settings):
        assert library_sync.is_stale() is True

    def test_a_fresh_cache_is_not(self, temp_db, plex):
        library_sync.run(plex)
        assert library_sync.is_stale() is False

    def test_an_old_cache_is(self, temp_db, plex):
        library_sync.run(plex)
        with db.session() as session:
            state = SyncState.load(session)
            state.last_sync_at = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
            session.add(state)
        assert library_sync.is_stale() is True

    def test_the_age_limit_is_configurable(self, temp_db, plex, library_settings):
        library_sync.run(plex)
        with db.session() as session:
            state = SyncState.load(session)
            state.last_sync_at = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
            session.add(state)

        assert library_sync.is_stale() is False
        library_settings(stale_after_hours=1)
        assert library_sync.is_stale() is True

    def test_an_unparseable_timestamp_reads_as_stale(self, temp_db, library_settings, plex):
        library_sync.run(plex)
        with db.session() as session:
            state = SyncState.load(session)
            state.last_sync_at = "not a date"
            session.add(state)
        assert library_sync.is_stale() is True
