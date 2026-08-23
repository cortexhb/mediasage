"""Tests for reading a review page down to its article prose."""

from contextlib import AbstractContextManager
from unittest.mock import AsyncMock, patch

import httpx

from backend.config import ResearchConfig
from backend.research.reviews import Reviews
from backend.research.safety import SafeFetcher
from tests.research.conftest import FakeHttp, response

ARTICLE = (
    "<html><body><article>"
    + "<p>Nevermind arrived in 1991 and rearranged the decade around it. " * 20
    + "</article><nav>Related stories</nav></body></html>"
)


def build(
    *answers: httpx.Response | Exception, config: ResearchConfig | None = None
) -> tuple[Reviews, FakeHttp]:
    http = FakeHttp(*answers)
    return Reviews(http, config or ResearchConfig()), http


def trimmed(text: str, max_chars: int, min_chars: int) -> str:
    """`Reviews.trimmed` over a client carrying those caps."""
    client, _ = build(
        config=ResearchConfig(review_max_chars=max_chars, review_min_chars=min_chars)
    )
    return client.trimmed(text)


def fetches(answer: object) -> AbstractContextManager[AsyncMock]:
    """Patch the safe fetch, so a test does not depend on DNS.

    `autospec` so the fetcher arrives as the first argument: it carries the
    hop limit, which one test below asserts on.
    """
    return patch.object(
        SafeFetcher, "get", autospec=True,
        side_effect=answer if isinstance(answer, Exception) else None,
        return_value=None if isinstance(answer, Exception) else answer,
    )


class TestPlainText:
    def test_it_recovers_the_article_prose(self):
        assert "rearranged the decade" in Reviews.plain_text(ARTICLE)

    def test_it_strips_the_markup(self):
        assert "<p>" not in Reviews.plain_text(ARTICLE)

    def test_it_collapses_whitespace(self):
        assert "  " not in Reviews.plain_text("<html><body><p>a\n\n\tb</p></body></html>")


class TestTrimmed:
    def test_a_short_review_is_returned_whole(self):
        assert trimmed("short", 2000, 1500) == "short"

    def test_it_cuts_on_a_sentence_end(self):
        text = "A" * 1600 + ". " + "B" * 600

        cut = trimmed(text, 2000, 1500)

        assert cut.endswith(".")
        assert "B" not in cut

    def test_a_sentence_end_below_the_floor_is_ignored(self):
        """Cutting there would throw away more than the tidy ending is worth."""
        text = "A" * 100 + ". " + "B" * 2500

        assert len(trimmed(text, 2000, 1500)) == 2000

    def test_the_cap_is_the_caller_s(self):
        assert len(trimmed("A" * 5000, 500, 400)) == 500


class TestText:
    async def test_it_returns_the_trimmed_article(self):
        client, _ = build()

        with fetches(response(text=ARTICLE)):
            found = await client.text("https://pitchfork.com/reviews/albums/1")

        assert found is not None
        assert "rearranged the decade" in found
        assert len(found) <= ResearchConfig().review_max_chars

    async def test_a_blocked_host_is_never_fetched(self):
        """AllMusic's terms prohibit automated access."""
        client, _ = build()

        with fetches(response(text=ARTICLE)) as fetch:
            assert await client.text("https://www.allmusic.com/album/x") is None

        fetch.assert_not_called()

    async def test_the_blocked_list_is_configurable(self):
        client, _ = build(config=ResearchConfig(blocked_review_hosts=["pitchfork.com"]))

        with fetches(response(text=ARTICLE)) as fetch:
            assert await client.text("https://pitchfork.com/reviews/albums/1") is None

        fetch.assert_not_called()

    async def test_an_unsafe_url_reads_as_no_review(self):
        client, _ = build()

        with fetches(None):
            assert await client.text("https://internal.lan/review") is None

    async def test_a_server_error_reads_as_no_review(self):
        client, _ = build()

        with fetches(response(status=500, text=ARTICLE)):
            assert await client.text("https://pitchfork.com/reviews/albums/1") is None

    async def test_a_transport_error_reads_as_no_review(self):
        client, _ = build()

        with fetches(httpx.ConnectError("refused")):
            assert await client.text("https://pitchfork.com/reviews/albums/1") is None

    async def test_a_page_with_no_prose_reads_as_no_review(self):
        client, _ = build()

        with fetches(response(text="<html><body></body></html>")):
            assert await client.text("https://pitchfork.com/reviews/albums/1") is None

    async def test_the_cap_is_configurable(self):
        client, _ = build(config=ResearchConfig(review_max_chars=200, review_min_chars=100))

        with fetches(response(text=ARTICLE)):
            found = await client.text("https://pitchfork.com/reviews/albums/1")

        assert found is not None
        assert len(found) <= 200

    async def test_the_hop_limit_is_passed_through(self):
        client, _ = build(config=ResearchConfig(max_redirects=2))

        with fetches(response(text=ARTICLE)) as fetch:
            await client.text("https://pitchfork.com/reviews/albums/1")

        assert fetch.call_args[0][0].max_redirects == 2
