"""Tests for the research pipeline that runs one album past all four sources."""

from unittest.mock import AsyncMock, MagicMock, patch

from backend.config import MediasageConfig, ResearchConfig
from backend.config.store import config_store
from backend.research.album import AlbumResearch
from backend.research.models import ReleaseDetail, ReleaseGroup
from tests.research.conftest import FakeHttp


def build(**sources: object) -> AlbumResearch:
    """A pipeline whose four sources are replaced by stand-ins.

    Every source is stubbed by default, so a test scripts only the one it is
    about and the rest contribute nothing -- which is the failure path anyway.
    """
    research = AlbumResearch(http=FakeHttp(), config=ResearchConfig())

    research.musicbrainz = MagicMock()
    research.musicbrainz.search = AsyncMock(return_value=None)
    research.musicbrainz.release_group = AsyncMock(return_value=None)
    research.musicbrainz.release = AsyncMock(return_value=None)
    research.wikipedia = MagicMock()
    research.wikipedia.summary = AsyncMock(return_value=None)
    research.wikipedia.article_for = AsyncMock(return_value=None)
    research.covers = MagicMock()
    research.covers.front = AsyncMock(return_value=None)
    research.reviews = MagicMock()
    research.reviews.text = AsyncMock(return_value=None)

    for name, source in sources.items():
        setattr(research, name, source)
    return research


def musicbrainz(
    mbid: str | None = "mbid-1",
    group: ReleaseGroup | None = None,
    release: ReleaseDetail | None = None,
) -> MagicMock:
    """A MusicBrainz stand-in answering with what a test hands in."""
    source = MagicMock()
    source.search = AsyncMock(return_value=mbid)
    source.release_group = AsyncMock(return_value=group)
    source.release = AsyncMock(return_value=release)
    return source


class TestOfAlbum:
    async def test_an_album_that_is_not_in_musicbrainz_yields_nothing(self):
        """The MBID doubles as the "this album exists" signal."""
        found = await build().of_album("Nobody", "Nothing")

        assert found.musicbrainz_id is None
        assert found.track_listing == []

    async def test_it_keeps_the_mbid_even_when_the_lookup_fails(self):
        found = await build(musicbrainz=musicbrainz()).of_album("Nirvana", "Nevermind")

        assert found.musicbrainz_id == "mbid-1"
        assert found.release_date is None

    async def test_it_reads_the_release_group_fields(self):
        group = ReleaseGroup(
            release_date="1991-09-24",
            review_urls=["https://pitchfork.com/1"],
            earliest_release_mbid="rel-1",
        )
        found = await build(musicbrainz=musicbrainz(group=group)).of_album("Nirvana", "Nevermind")

        assert found.release_date == "1991-09-24"
        assert found.review_links == ["https://pitchfork.com/1"]
        assert found.earliest_release_mbid == "rel-1"

    async def test_it_reads_the_earliest_release_detail(self):
        group = ReleaseGroup(earliest_release_mbid="rel-1")
        release = ReleaseDetail(track_listing=["In Bloom"], label="DGC")

        found = await build(
            musicbrainz=musicbrainz(group=group, release=release)
        ).of_album("Nirvana", "Nevermind")

        assert found.track_listing == ["In Bloom"]
        assert found.label == "DGC"

    async def test_light_research_skips_the_article_and_reviews(self):
        """A secondary pick is shown as one line, so the long sources are waste."""
        research = build(musicbrainz=musicbrainz(group=ReleaseGroup(
            wikipedia_url="https://en.wikipedia.org/wiki/Nevermind",
            review_urls=["https://pitchfork.com/1"],
        )))

        await research.of_album("Nirvana", "Nevermind", full=False)

        research.wikipedia.summary.assert_not_called()
        research.reviews.text.assert_not_called()

    async def test_full_research_reads_the_article(self):
        research = build(musicbrainz=musicbrainz(group=ReleaseGroup(
            wikipedia_url="https://en.wikipedia.org/wiki/Nevermind",
        )))
        research.wikipedia.summary = AsyncMock(return_value="It is an album.")

        found = await research.of_album("Nirvana", "Nevermind")

        assert found.wikipedia_summary == "It is an album."

    async def test_it_resolves_an_article_through_wikidata(self):
        """Some release groups carry only a Wikidata relation."""
        research = build(musicbrainz=musicbrainz(group=ReleaseGroup(
            wikidata_url="https://www.wikidata.org/wiki/Q207289",
        )))
        research.wikipedia.article_for = AsyncMock(
            return_value="https://en.wikipedia.org/wiki/Nevermind"
        )
        research.wikipedia.summary = AsyncMock(return_value="It is an album.")

        found = await research.of_album("Nirvana", "Nevermind")

        assert found.wikipedia_summary == "It is an album."
        research.wikipedia.article_for.assert_awaited_once()

    async def test_a_release_group_with_no_article_reads_nothing(self):
        research = build(musicbrainz=musicbrainz(group=ReleaseGroup()))

        found = await research.of_album("Nirvana", "Nevermind")

        assert found.wikipedia_summary is None
        research.wikipedia.summary.assert_not_called()

    async def test_it_keeps_only_the_reviews_it_could_read(self):
        research = build(musicbrainz=musicbrainz(group=ReleaseGroup(
            review_urls=["https://a.test/1", "https://b.test/2"],
        )))
        research.reviews.text = AsyncMock(side_effect=["first review", None])

        found = await research.of_album("Nirvana", "Nevermind")

        assert found.review_texts == ["first review"]

    async def test_the_library_year_is_passed_to_the_search(self):
        """It disambiguates a title several artists have used."""
        research = build(musicbrainz=musicbrainz())

        await research.of_album("Nirvana", "Greatest Hits", year=1991)

        assert research.musicbrainz.search.call_args.kwargs["year"] == 1991


class TestCoverArt:
    async def test_it_asks_for_both_mbids(self):
        research = build()
        research.covers.front = AsyncMock(return_value="https://cdn.test/front.jpg")

        assert await research.cover_art("rel-1", "grp-1") == "https://cdn.test/front.jpg"
        research.covers.front.assert_awaited_once_with("rel-1", "grp-1")

    async def test_a_missing_group_mbid_becomes_an_empty_string(self):
        research = build()

        await research.cover_art("rel-1")

        research.covers.front.assert_awaited_once_with("rel-1", "")


class TestConstruction:
    def test_it_reads_the_settings_from_the_store(self):
        """The client is held for the process, so the settings are read once."""
        config = MediasageConfig(
            llm={"provider": "anthropic", "context_window": 200000},
            research=ResearchConfig(musicbrainz_interval=2.0, request_timeout=3.0),
        )
        with patch.object(config_store, "config", config):
            research = AlbumResearch(http=FakeHttp())

        assert research.config.musicbrainz_interval == 2.0
        assert research.musicbrainz.throttle.interval == 2.0

    async def test_closing_releases_the_shared_client(self):
        http = FakeHttp()
        http.close = AsyncMock()
        research = AlbumResearch(http=http, config=ResearchConfig())

        await research.close()

        http.close.assert_awaited_once()
