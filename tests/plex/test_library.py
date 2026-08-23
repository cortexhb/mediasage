"""Tests for reading the Plex library: paging, metadata, queries."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError

from backend.config.store import config_store
from backend.library import AlbumMetadata
from backend.models import Track
from backend.plex.connection import PlexFetchError, PlexQueryError
from backend.plex.filters import PlexFilter
from backend.plex.library import PlexLibrary
from tests.plex.conftest import choice, make_connection, raw_track


def fake_items(count: int, start: int = 0) -> list[MagicMock]:
    """Stub Plex objects with sequential rating keys."""
    items = []
    for index in range(start, start + count):
        item = MagicMock()
        item.ratingKey = index
        items.append(item)
    return items


def paged(section: MagicMock, items: list[object], page_size: int) -> None:
    """Make `section.search` serve `items` in pages of `page_size`."""
    def search(**kwargs):
        start = kwargs.get("container_start", 0)
        return items[start : start + page_size]

    section.search.side_effect = search


class TestTotalTracks:
    """The library's size, or nothing when it cannot be read."""

    def test_it_comes_from_the_section(self, connection, section):
        section.totalViewSize.return_value = 4200
        assert PlexLibrary(connection=connection).total_tracks() == 4200

    def test_a_disconnected_library_reports_zero(self):
        assert PlexLibrary(connection=make_connection()).total_tracks() == 0

    def test_a_failing_call_reports_zero(self, connection, section):
        section.totalViewSize.side_effect = RuntimeError("boom")
        assert PlexLibrary(connection=connection).total_tracks() == 0


class TestIterRawTracks:
    """Paging is what makes the sync resumable."""

    def test_it_pages_until_a_short_page(self, connection, section):
        paged(section, fake_items(2500), config_store.get().plex.page_size)
        pages = list(PlexLibrary(connection=connection).iter_raw_tracks())
        assert [len(page) for page in pages] == [1000, 1000, 500]

    def test_each_request_is_bounded_by_the_configured_page(self, connection, section, tuned):
        tuned("plex", page_size=5)
        paged(section, fake_items(10), 5)
        list(PlexLibrary(connection=connection).iter_raw_tracks())

        first = section.search.call_args_list[0].kwargs
        assert first["libtype"] == "track"
        assert (first["container_size"], first["maxresults"]) == (5, 5)

    def test_it_resumes_from_an_offset(self, connection, section):
        paged(section, fake_items(10), config_store.get().plex.page_size)
        list(PlexLibrary(connection=connection).iter_raw_tracks(start=4))
        assert section.search.call_args_list[0].kwargs["container_start"] == 4

    def test_an_empty_library_yields_nothing(self, connection, section):
        section.search.return_value = []
        assert list(PlexLibrary(connection=connection).iter_raw_tracks()) == []

    def test_a_disconnected_library_yields_nothing(self):
        assert list(PlexLibrary(connection=make_connection()).iter_raw_tracks()) == []

    def test_a_failing_page_is_retried(self, connection, section, no_sleep):
        calls = []

        def search(**kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise RequestsConnectionError("refused")
            return fake_items(3)

        section.search.side_effect = search
        assert len(list(PlexLibrary(connection=connection).iter_raw_tracks())) == 1

    def test_exhausted_retries_propagate(self, connection, section, no_sleep):
        section.search.side_effect = RequestsConnectionError("refused")
        with pytest.raises(PlexFetchError):
            list(PlexLibrary(connection=connection).iter_raw_tracks())


class TestAllRawTracks:
    """The whole library at once, for callers that can hold it."""

    def test_it_flattens_every_page(self, connection, section):
        paged(section, fake_items(2500), config_store.get().plex.page_size)
        assert len(PlexLibrary(connection=connection).all_raw_tracks()) == 2500

    def test_a_failure_is_empty_not_fatal(self, connection, section, no_sleep):
        section.search.side_effect = RequestsConnectionError("refused")
        assert PlexLibrary(connection=connection).all_raw_tracks() == []


class TestAlbumMetadataFetch:
    """Genres must never be read off the album objects themselves."""

    def test_genres_come_from_per_genre_queries(self, connection, section):
        albums = fake_items(2)
        for album in albums:
            album.year = 1999

        section.listFilterChoices.return_value = [choice("Rock"), choice("Jazz")]

        def search(**kwargs):
            if kwargs.get("genre") == "Rock":
                return [albums[0]]
            if kwargs.get("genre") == "Jazz":
                return [albums[1]]
            return albums if kwargs.get("container_start", 0) == 0 else []

        section.search.side_effect = search
        metadata = PlexLibrary(connection=connection).album_metadata()

        assert metadata["0"] == AlbumMetadata(genres=["Rock"], year=1999)
        assert metadata["1"] == AlbumMetadata(genres=["Jazz"], year=1999)

    def test_the_genres_attribute_is_never_read(self, connection, section):
        """Reading album.genres is what triggers the per-album refetch storm."""
        album = MagicMock()
        album.ratingKey = 1
        album.year = 2000
        probe = MagicMock(side_effect=AssertionError("album.genres was read"))
        type(album).genres = property(lambda self: probe())

        section.listFilterChoices.return_value = []
        section.search.side_effect = (
            lambda **kw: [album] if kw.get("container_start", 0) == 0 else []
        )

        assert PlexLibrary(connection=connection).album_metadata()["1"].genres == []

    def test_a_server_without_genre_filters_still_yields_years(self, connection, section):
        album = fake_items(1)[0]
        album.year = 1985
        section.listFilterChoices.side_effect = RuntimeError("not supported")
        section.search.side_effect = (
            lambda **kw: [album] if kw.get("container_start", 0) == 0 else []
        )

        assert PlexLibrary(connection=connection).album_metadata()["0"] == AlbumMetadata(year=1985)

    def test_one_failing_genre_does_not_fail_the_rest(self, connection, section):
        album = fake_items(1)[0]
        album.year = 1985
        section.listFilterChoices.return_value = [choice("Broken"), choice("Rock")]

        def search(**kwargs):
            if kwargs.get("genre") == "Broken":
                raise RuntimeError("filter blew up")
            if kwargs.get("genre") == "Rock":
                return [album]
            return [album] if kwargs.get("container_start", 0) == 0 else []

        section.search.side_effect = search
        assert PlexLibrary(connection=connection).album_metadata()["0"].genres == ["Rock"]

    def test_a_disconnected_library_has_no_albums(self):
        assert PlexLibrary(connection=make_connection()).album_metadata() == {}


class TestStats:
    """The filter choices the UI offers."""

    def test_it_reports_genres_decades_and_the_total(self, connection, section):
        section.listFilterChoices.side_effect = [
            [choice("Rock"), choice("Alternative")],
            [choice("1990"), choice("2000s")],
        ]
        section.totalViewSize.return_value = 500

        stats = PlexLibrary(connection=connection).stats()

        assert stats.total_tracks == 500
        assert [genre.name for genre in stats.genres] == ["Alternative", "Rock"]
        assert [decade.name for decade in stats.decades] == ["1990s", "2000s"]

    def test_counts_are_absent_because_plex_does_not_report_them(self, connection, section):
        section.listFilterChoices.side_effect = [[choice("Rock")], []]
        section.totalViewSize.return_value = 1
        assert PlexLibrary(connection=connection).stats().genres[0].count is None

    def test_a_broken_server_raises_rather_than_reading_as_empty(self, connection, section):
        section.listFilterChoices.side_effect = RuntimeError("boom")
        with pytest.raises(PlexQueryError):
            PlexLibrary(connection=connection).stats()

    def test_a_disconnected_library_raises(self):
        with pytest.raises(PlexQueryError):
            PlexLibrary(connection=make_connection()).stats()


class TestFiltered:
    """Filtered queries, and the live versions dropped afterwards."""

    def test_an_unlimited_query_asks_plex_for_everything_matching(
        self, connection, section, library_settings
    ):
        section.search.return_value = [raw_track("1")]
        PlexLibrary(connection=connection).filtered(PlexFilter(genres=["Rock"], exclude_live=False))

        assert section.search.call_args.kwargs == {"libtype": "track", "genre": ["Rock"]}

    def test_a_limited_query_samples_at_random(self, connection, section, library_settings):
        section.search.return_value = [raw_track(str(i)) for i in range(20)]
        tracks = PlexLibrary(connection=connection).filtered(PlexFilter(exclude_live=False), limit=5)

        assert section.search.call_args.kwargs["sort"] == "random"
        assert len(tracks) == 5

    def test_live_versions_are_dropped_after_the_fetch(
        self, connection, section, library_settings
    ):
        section.search.return_value = [
            raw_track("1", "Song"),
            raw_track("2", "Song (Live)"),
            raw_track("3", "Song", album="Live at Wembley"),
        ]
        tracks = PlexLibrary(connection=connection).filtered(PlexFilter(exclude_live=True))
        assert [track.rating_key for track in tracks] == ["1"]

    def test_the_configured_keywords_decide_what_is_live(
        self, connection, section, library_settings
    ):
        library_settings(live_keywords=["unplugged"], dated_titles_are_live=False)
        section.search.return_value = [raw_track("1", "Song (Live)"), raw_track("2", "Unplugged")]

        tracks = PlexLibrary(connection=connection).filtered(PlexFilter(exclude_live=True))
        assert [track.rating_key for track in tracks] == ["1"]

    def test_a_failing_query_raises(self, connection, section, library_settings):
        section.search.side_effect = RuntimeError("boom")
        with pytest.raises(PlexQueryError):
            PlexLibrary(connection=connection).filtered(PlexFilter())

    def test_a_disconnected_library_returns_nothing(self, library_settings):
        assert PlexLibrary(connection=make_connection()).filtered(PlexFilter()) == []


class TestCount:
    """Counting without building models."""

    def test_an_unfiltered_count_uses_the_total(self, connection, section, library_settings):
        section.totalViewSize.return_value = 4200
        assert PlexLibrary(connection=connection).count(PlexFilter(exclude_live=False)) == 4200
        section.search.assert_not_called()

    def test_a_filtered_count_counts_the_rows(self, connection, section, library_settings):
        section.search.return_value = [raw_track("1"), raw_track("2")]
        assert PlexLibrary(connection=connection).count(PlexFilter(genres=["Rock"], exclude_live=False)) == 2

    def test_live_versions_are_excluded_from_the_count(
        self, connection, section, library_settings
    ):
        section.search.return_value = [raw_track("1", "Song"), raw_track("2", "Song (Live)")]
        assert PlexLibrary(connection=connection).count(PlexFilter(exclude_live=True)) == 1

    def test_a_failing_count_raises_rather_than_returning_a_sentinel(
        self, connection, section, library_settings
    ):
        section.search.side_effect = RuntimeError("boom")
        with pytest.raises(PlexQueryError):
            PlexLibrary(connection=connection).count(PlexFilter(genres=["Rock"]))

    def test_a_disconnected_library_raises(self, library_settings):
        with pytest.raises(PlexQueryError):
            PlexLibrary(connection=make_connection()).count(PlexFilter())


class TestSearch:
    """Title search first, artists filling the remainder."""

    def test_titles_are_searched(self, connection, section, library_settings):
        section.searchTracks.return_value = [raw_track("1", "Karma Police")]
        section.searchArtists.return_value = []

        tracks = PlexLibrary(connection=connection).search("karma", limit=10)

        assert [track.title for track in tracks] == ["Karma Police"]
        assert section.searchTracks.call_args.kwargs == {"title": "karma", "limit": 10}

    def test_artists_are_searched_for_real_not_filtered_in_python(
        self, connection, section, library_settings
    ):
        section.searchTracks.return_value = []
        artist = MagicMock()
        artist.tracks.return_value = [raw_track("7", "Paranoid Android", artist="Radiohead")]
        section.searchArtists.return_value = [artist]

        tracks = PlexLibrary(connection=connection).search("radiohead", limit=10)

        assert [track.rating_key for track in tracks] == ["7"]
        assert section.searchArtists.call_args.kwargs == {"title": "radiohead", "limit": 10}

    def test_an_artist_track_already_found_is_not_repeated(
        self, connection, section, library_settings
    ):
        found = raw_track("1", "Creep")
        section.searchTracks.return_value = [found]
        artist = MagicMock()
        artist.tracks.return_value = [found, raw_track("2", "Creep (Acoustic)")]
        section.searchArtists.return_value = [artist]

        tracks = PlexLibrary(connection=connection).search("creep", limit=10)
        assert [track.rating_key for track in tracks] == ["1", "2"]

    def test_the_limit_is_honoured(self, connection, section, library_settings):
        section.searchTracks.return_value = [raw_track("1"), raw_track("2"), raw_track("3")]
        assert len(PlexLibrary(connection=connection).search("song", limit=2)) == 2

    def test_a_full_page_of_titles_skips_the_artist_search(
        self, connection, section, library_settings
    ):
        section.searchTracks.return_value = [raw_track("1"), raw_track("2")]
        PlexLibrary(connection=connection).search("song", limit=2)
        section.searchArtists.assert_not_called()

    def test_a_failing_search_is_empty_not_fatal(self, connection, section, library_settings):
        section.searchTracks.side_effect = RuntimeError("boom")
        assert PlexLibrary(connection=connection).search("song") == []


class TestTrackByKey:
    """One track, by rating key."""

    def test_it_converts_what_plex_returns(self, connection, server):
        server.fetchItem.return_value = raw_track("42", "Song")
        track = PlexLibrary(connection=connection).track_by_key("42")
        assert track is not None
        assert (track.rating_key, track.title) == ("42", "Song")

    def test_an_unresolvable_key_is_none(self, connection, server):
        server.fetchItem.side_effect = RuntimeError("gone")
        assert PlexLibrary(connection=connection).track_by_key("42") is None

    def test_a_disconnected_server_is_none(self):
        assert PlexLibrary(connection=make_connection()).track_by_key("42") is None


class TestThumbPath:
    """Art is walked up the hierarchy so compilations are not blank."""

    @pytest.mark.parametrize(
        ("attributes", "expected"),
        [
            ({"thumb": "/track", "parentThumb": "/album", "grandparentThumb": "/artist"}, "/track"),
            ({"thumb": None, "parentThumb": "/album", "grandparentThumb": "/artist"}, "/album"),
            ({"thumb": None, "parentThumb": None, "grandparentThumb": "/artist"}, "/artist"),
            ({"thumb": None, "parentThumb": None, "grandparentThumb": None}, None),
        ],
    )
    def test_it_falls_back_down_the_hierarchy(self, connection, server, attributes, expected):
        server.fetchItem.return_value = SimpleNamespace(**attributes)
        assert PlexLibrary(connection=connection).thumb_path("1") == expected

    def test_an_unresolvable_key_has_no_thumb(self, connection, server):
        server.fetchItem.side_effect = RuntimeError("gone")
        assert PlexLibrary(connection=connection).thumb_path("1") is None


class TestTrackOfPlex:
    """Converting a raw Plex object into the API's model."""

    def test_it_reads_the_fields_the_api_returns(self):
        track = Track.of_plex(raw_track("1", "Song", artist="Artist", album="Album"))

        assert (track.rating_key, track.title, track.artist, track.album) == (
            "1", "Song", "Artist", "Album",
        )
        assert track.genres == ["Rock"]

    def test_art_is_proxied_rather_than_linked_to_plex(self):
        assert Track.of_plex(raw_track("9")).art_url == "/api/art/9"

    def test_a_missing_artist_and_album_get_placeholders(self):
        raw = raw_track("1")
        raw.grandparentTitle = None
        raw.parentTitle = None
        track = Track.of_plex(raw)
        assert (track.artist, track.album) == ("Unknown Artist", "Unknown Album")

    def test_the_year_falls_back_to_the_track(self):
        raw = raw_track("1", year=None)
        raw.year = 1977
        assert Track.of_plex(raw).year == 1977


class TestPageSize:
    """A NAS answers a big page slower than a desktop, so the size is tunable."""

    def test_a_bulk_fetch_uses_it(self, connection, section, tuned):
        tuned("plex", page_size=7)
        paged(section, fake_items(10), 7)

        list(PlexLibrary(connection=connection).iter_raw_tracks())

        assert section.search.call_args_list[0].kwargs["container_size"] == 7
