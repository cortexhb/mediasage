"""Tests for finding an album in MusicBrainz and reading what it knows."""

import httpx
import pytest

from backend.config import ResearchConfig
from backend.research.http import Throttle
from backend.research.musicbrainz import MusicBrainz, without_edition
from tests.research.conftest import FakeHttp, response


def groups(*entries: dict) -> dict:
    """A release-group search response carrying `entries`."""
    return {"release-groups": list(entries)}


def entry(mbid: str, title: str, artist: str = "Nirvana", **extra: object) -> dict:
    """One search hit, with the fields the scorer reads."""
    return {"id": mbid, "title": title, "artist-credit": [{"name": artist}], **extra}


def build(*answers: object, config: ResearchConfig | None = None) -> tuple[MusicBrainz, FakeHttp]:
    """A client over scripted answers, with the rate limit switched off."""
    http = FakeHttp(*answers)
    settings = config or ResearchConfig()
    return MusicBrainz(http, Throttle(0), settings), http


class TestWithoutEdition:
    @pytest.mark.parametrize("album,stripped", (
        ("Nevermind (Deluxe Edition)", "Nevermind"),
        ("Ten (Super Deluxe)", "Ten"),
        ("Ágætis byrjun (Anniversary Edition)", "Ágætis byrjun"),
    ))
    def test_strips_an_edition_suffix(self, album, stripped):
        assert without_edition(album) == stripped

    def test_leaves_a_title_with_no_suffix_alone(self):
        assert without_edition("Nevermind") is None

    def test_an_unlisted_marker_is_left_alone(self):
        """The alternation is a fixed list; "Remastered" leading is not on it."""
        assert without_edition("Nevermind (Remastered 2011)") is None

    def test_a_marker_inside_the_title_is_part_of_it(self):
        """Only the end is stripped: "Deluxe" mid-title is the real name."""
        assert without_edition("Deluxe Trouble") is None


class TestSearch:
    async def test_a_strict_hit_wins_immediately(self):
        client, http = build(response(groups(entry("mbid-1", "Nevermind"))))

        assert await client.search("Nirvana", "Nevermind") == "mbid-1"
        assert len(http.calls) == 1

    async def test_the_strict_query_names_both_halves(self):
        client, http = build(response(groups(entry("mbid-1", "Nevermind"))))
        await client.search("Nirvana", "Nevermind")

        query = http.calls[0][1]["params"]["query"]
        assert 'artist:"Nirvana"' in query
        assert 'releasegroup:"Nevermind"' in query

    async def test_it_retries_without_the_edition_suffix(self):
        client, http = build(
            response(groups()),
            response(groups(entry("mbid-2", "Nevermind"))),
        )

        assert await client.search("Nirvana", "Nevermind (Deluxe Edition)") == "mbid-2"
        assert 'releasegroup:"Nevermind"' in http.calls[1][1]["params"]["query"]

    async def test_it_falls_back_to_the_album_alone(self):
        """Plex files a soundtrack under a performer, MusicBrainz under the composer."""
        client, http = build(
            response(groups()),
            response(groups(entry("mbid-3", "The Mission", artist="Ennio Morricone"))),
        )

        assert await client.search("Yo-Yo Ma", "The Mission") == "mbid-3"
        assert "artist:" not in http.calls[1][1]["params"]["query"]

    async def test_it_picks_the_best_scoring_fallback(self):
        client, _ = build(
            response(groups()),
            response(groups(
                entry("wrong", "Ten Live", artist="Somebody"),
                entry("right", "Ten", artist="Pearl Jam", **{"primary-type": "Album"}),
            )),
        )

        assert await client.search("Pearl Jam", "Ten") == "right"

    async def test_nothing_anywhere_reports_nothing(self):
        client, _ = build(response(groups()), response(groups()))

        assert await client.search("Nobody", "Nothing") is None

    async def test_an_entry_without_an_id_is_skipped(self):
        client, _ = build(
            response(groups({"title": "Nevermind"})),
            response(groups()),
        )

        assert await client.search("Nirvana", "Nevermind") is None

    async def test_the_year_disambiguates_a_common_title(self):
        client, _ = build(
            response(groups()),
            response(groups(
                entry("later", "Greatest Hits", **{"first-release-date": "2005-01-01"}),
                entry("wanted", "Greatest Hits", **{"first-release-date": "1991-01-01"}),
            )),
        )

        assert await client.search("Nirvana", "Greatest Hits", year=1991) == "wanted"


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

        assert group.wikipedia_url.endswith("/Nevermind")
        assert group.earliest_release_mbid == "rel-1"
        assert "release-group/mbid-1" in http.urls[0]

    async def test_release_parses_its_track_listing(self):
        client, _ = build(response({"media": [{"tracks": [{"title": "In Bloom"}]}]}))

        assert (await client.release("rel-1")).track_listing == ["In Bloom"]

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
        answer = response()
        answer.json.side_effect = ValueError("not json")
        client, _ = build(answer)

        assert await client.release_group("mbid-1") is None

    async def test_a_failed_search_reports_nothing_found(self):
        client, _ = build(httpx.ConnectError("refused"), httpx.ConnectError("refused"))

        assert await client.search("Nirvana", "Nevermind") is None
