"""Tests for finding an album in MusicBrainz and reading what it knows."""

import httpx

from backend.config import ResearchConfig
from backend.recommender import AlbumRef
from backend.research.http import Throttle
from backend.research.musicbrainz import MusicBrainz
from tests.research.conftest import FakeHttp, response


def groups(*entries: dict) -> dict:
    """A release-group search response carrying `entries`."""
    return {"release-groups": list(entries)}


def entry(mbid: str, title: str, artist: str = "Nirvana", **extra: object) -> dict:
    """One search hit, with the fields the scorer reads."""
    return {"id": mbid, "title": title, "artist-credit": [{"name": artist}], **extra}


def build(
    *answers: httpx.Response | Exception, config: ResearchConfig | None = None
) -> tuple[MusicBrainz, FakeHttp]:
    """A client over scripted answers, with the rate limit switched off."""
    http = FakeHttp(*answers)
    settings = config or ResearchConfig()
    return MusicBrainz(http, Throttle(0), settings), http


class TestSearch:
    async def test_a_strict_hit_wins_immediately(self):
        client, http = build(response(groups(entry("mbid-1", "Nevermind"))))

        assert await client.search(AlbumRef(artist="Nirvana", album="Nevermind")) == "mbid-1"
        assert len(http.calls) == 1

    async def test_the_strict_query_names_both_halves(self):
        client, http = build(response(groups(entry("mbid-1", "Nevermind"))))
        await client.search(AlbumRef(artist="Nirvana", album="Nevermind"))

        query = http.calls[0][1]["params"]["query"]
        assert 'artist:"Nirvana"' in query
        assert 'releasegroup:"Nevermind"' in query

    async def test_it_retries_without_the_edition_suffix(self):
        client, http = build(
            response(groups()),
            response(groups(entry("mbid-2", "Nevermind"))),
        )

        assert await client.search(AlbumRef(artist="Nirvana", album="Nevermind (Deluxe Edition)")) == "mbid-2"
        assert 'releasegroup:"Nevermind"' in http.calls[1][1]["params"]["query"]

    async def test_it_falls_back_to_the_album_alone(self):
        """Plex files a soundtrack under a performer, MusicBrainz under the composer."""
        client, http = build(
            response(groups()),
            response(groups(entry("mbid-3", "The Mission", artist="Ennio Morricone"))),
        )

        assert await client.search(AlbumRef(artist="Yo-Yo Ma", album="The Mission")) == "mbid-3"
        assert "artist:" not in http.calls[1][1]["params"]["query"]

    async def test_it_picks_the_best_scoring_fallback(self):
        client, _ = build(
            response(groups()),
            response(groups(
                entry("wrong", "Ten Live", artist="Somebody"),
                entry("right", "Ten", artist="Pearl Jam", **{"primary-type": "Album"}),
            )),
        )

        assert await client.search(AlbumRef(artist="Pearl Jam", album="Ten")) == "right"

    async def test_nothing_anywhere_reports_nothing(self):
        client, _ = build(response(groups()), response(groups()))

        assert await client.search(AlbumRef(artist="Nobody", album="Nothing")) is None

    async def test_an_entry_without_an_id_is_skipped(self):
        client, _ = build(
            response(groups({"title": "Nevermind"})),
            response(groups()),
        )

        assert await client.search(AlbumRef(artist="Nirvana", album="Nevermind")) is None

    async def test_the_year_disambiguates_a_common_title(self):
        client, _ = build(
            response(groups()),
            response(groups(
                entry("later", "Greatest Hits", **{"first-release-date": "2005-01-01"}),
                entry("wanted", "Greatest Hits", **{"first-release-date": "1991-01-01"}),
            )),
        )

        assert await client.search(AlbumRef(artist="Nirvana", album="Greatest Hits"), year=1991) == "wanted"


class TestLookups:
    async def test_release_group_parses_its_relations(self):
        client, http = build(response({
            "relations": [{
                "type": "wikipedia",
                "url": {"resource": "https://en.wikipedia.org/wiki/Nevermind"},
            }],
            "releases": [{"id": "rel-1", "date": "1991-09-24"}],
        }))

        group = await client.release_group("mbid-1")

        assert group is not None
        assert group.wikipedia_url.endswith("/Nevermind")
        assert group.earliest_release_mbid == "rel-1"
        assert "release-group/mbid-1" in http.urls[0]

    async def test_release_parses_its_track_listing(self):
        client, _ = build(response({"media": [{"tracks": [{"title": "In Bloom"}]}]}))

        release = await client.release("rel-1")

        assert release is not None
        assert release.track_listing == ["In Bloom"]

    async def test_the_base_url_is_configurable(self):
        """A self-hoster can run the official MusicBrainz mirror."""
        client, http = build(
            response({}), config=ResearchConfig(musicbrainz_url="http://mb.lan/ws/2")
        )
        await client.release_group("mbid-1")

        assert http.urls[0] == "http://mb.lan/ws/2/release-group/mbid-1"


class TestFailure:
    async def test_a_transport_error_reads_as_no_answer(self):
        """Research grounds a pitch, it does not gate one."""
        client, _ = build(httpx.ConnectError("refused"))

        assert await client.release_group("mbid-1") is None

    async def test_a_server_error_reads_as_no_answer(self):
        client, _ = build(response(status=503))

        assert await client.release("rel-1") is None

    async def test_unparseable_json_reads_as_no_answer(self):
        client, _ = build(response(text="not json at all"))

        assert await client.release_group("mbid-1") is None

    async def test_a_failed_search_reports_nothing_found(self):
        client, _ = build(httpx.ConnectError("refused"), httpx.ConnectError("refused"))

        assert await client.search(AlbumRef(artist="Nirvana", album="Nevermind")) is None
