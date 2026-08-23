"""Tests for the Cover Art Archive lookup, release then release group."""

import httpx

from backend.config import ResearchConfig
from backend.research.covers import CoverArt
from tests.research.conftest import FakeHttp, response

CDN = "https://ia800123.us.archive.org/front.jpg"


def build(
    *answers: httpx.Response | Exception, config: ResearchConfig | None = None
) -> tuple[CoverArt, FakeHttp]:
    http = FakeHttp(*answers)
    return CoverArt(http, config or ResearchConfig()), http


class TestFront:
    async def test_the_release_answers_first(self):
        client, http = build(response(url=CDN))

        assert await client.front("rel-1", "grp-1") == CDN
        assert "release/rel-1/front" in http.urls[0]

    async def test_it_falls_back_to_the_release_group(self):
        """A specific release often has no art while its group does."""
        client, http = build(response(status=404), response(url=CDN))

        assert await client.front("rel-1", "grp-1") == CDN
        assert "release-group/grp-1/front" in http.urls[1]

    async def test_nothing_uploaded_anywhere_reads_as_no_art(self):
        client, _ = build(response(status=404), response(status=404))

        assert await client.front("rel-1", "grp-1") is None

    async def test_an_empty_mbid_is_not_looked_up(self):
        client, http = build(response(status=404))

        assert await client.front("rel-1", "") is None
        assert len(http.calls) == 1

    async def test_both_mbids_empty_costs_no_request(self):
        client, http = build()

        assert await client.front("", "") is None
        assert http.calls == []

    async def test_a_transport_error_reads_as_no_art(self):
        client, _ = build(httpx.ConnectError("refused"), httpx.ConnectError("refused"))

        assert await client.front("rel-1", "grp-1") is None

    async def test_it_follows_the_redirect_to_the_cdn(self):
        """The archive redirects; the final URL is what the art proxy fetches."""
        client, http = build(response(url=CDN))
        await client.front("rel-1")

        assert http.calls[0][1]["follow_redirects"] is True

    async def test_the_base_url_is_configurable(self):
        client, http = build(
            response(url=CDN), config=ResearchConfig(cover_art_url="http://caa.lan")
        )
        await client.front("rel-1")

        assert http.urls[0] == "http://caa.lan/release/rel-1/front"
