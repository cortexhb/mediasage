"""Tests for reading an article down to the part a pitch can use."""

import httpx

from backend.config import ResearchConfig
from backend.research.wikipedia import Wikipedia
from tests.research.conftest import FakeHttp, response


def extract(text: str) -> dict:
    """A MediaWiki extracts response carrying one page's plain text."""
    return {"query": {"pages": {"1234": {"extract": text}}}}


def build(
    *answers: httpx.Response | Exception, config: ResearchConfig | None = None
) -> tuple[Wikipedia, FakeHttp]:
    http = FakeHttp(*answers)
    return Wikipedia(http, config or ResearchConfig()), http


def sections(text: str, config: ResearchConfig | None = None) -> str:
    """`Wikipedia.useful_sections` over a client carrying those settings."""
    client, _ = build(config=config or ResearchConfig())
    return client.useful_sections(text)


class TestUsefulSections:
    def test_keeps_the_lead_section(self):
        """The lead has no title, so it is never matched by a drop keyword."""
        article = "Nevermind is the second studio album.\n\n== Charts ==\nrows"

        assert "second studio album" in sections(article)

    def test_drops_a_table_rendered_as_prose(self):
        article = "Lead.\n\n== Charts ==\nUS 1 UK 7\n\n== Recording ==\nSound City."

        kept = sections(article)

        assert "US 1 UK 7" not in kept
        assert "Sound City" in kept

    def test_a_dropped_section_ends_at_the_next_header(self):
        article = "Lead.\n\n== Personnel ==\nnames\n\n== Legacy ==\nit mattered"

        assert "it mattered" in sections(article)

    def test_the_drop_list_is_configurable(self):
        """A deployment that wants the personnel list can keep it."""
        article = "Lead.\n\n== Personnel ==\nKurt Cobain"

        assert "Kurt Cobain" in sections(article, ResearchConfig(wikipedia_drop_sections=["chart"]))

    def test_it_cuts_on_a_paragraph_break(self):
        article = "A" * 40 + "\n\n" + "B" * 200

        kept = sections(article, ResearchConfig(wikipedia_max_chars=60, wikipedia_drop_sections=[]))

        assert kept == "A" * 40

    def test_a_paragraph_longer_than_the_cap_is_cut_hard(self):
        config = ResearchConfig(wikipedia_max_chars=100, wikipedia_drop_sections=[])

        assert len(sections("A" * 500, config)) == 100

    def test_a_short_article_is_returned_whole(self):
        assert sections("short") == "short"


class TestSummary:
    async def test_it_reads_the_article_text(self):
        client, _ = build(response(extract("Nevermind is an album.")))

        assert await client.summary("https://en.wikipedia.org/wiki/Nevermind") == (
            "Nevermind is an album."
        )

    async def test_it_asks_for_the_decoded_title(self):
        """Percent escapes are decoded; MediaWiki takes the underscores as-is."""
        client, http = build(response(extract("text")))
        await client.summary("https://en.wikipedia.org/wiki/%C3%81g%C3%A6tis_byrjun")

        assert http.calls[0][1]["params"]["titles"] == "Ágætis_byrjun"

    async def test_a_url_that_is_not_an_article_is_refused(self):
        client, http = build()

        assert await client.summary("https://example.com/not-a-wiki") is None
        assert http.calls == []

    async def test_a_missing_page_reads_as_nothing(self):
        client, _ = build(response({"query": {"pages": {"-1": {}}}}))

        assert await client.summary("https://en.wikipedia.org/wiki/Nope") is None

    async def test_a_transport_error_reads_as_nothing(self):
        client, _ = build(httpx.ConnectError("refused"))

        assert await client.summary("https://en.wikipedia.org/wiki/Nevermind") is None

    async def test_the_api_url_is_configurable(self):
        client, http = build(
            response(extract("text")),
            config=ResearchConfig(wikipedia_api_url="http://wiki.lan/w/api.php"),
        )
        await client.summary("https://en.wikipedia.org/wiki/Nevermind")

        assert http.urls[0] == "http://wiki.lan/w/api.php"

    async def test_the_cap_is_configurable(self):
        client, _ = build(
            response(extract("A" * 500)), config=ResearchConfig(wikipedia_max_chars=50)
        )

        summary = await client.summary("https://en.wikipedia.org/wiki/X")

        assert summary is not None
        assert len(summary) == 50


class TestArticleFor:
    async def test_it_resolves_a_wikidata_item(self):
        """Some release groups carry only a Wikidata relation."""
        client, http = build(response({"url": "https://en.wikipedia.org/wiki/Nevermind"}))

        found = await client.article_for("https://www.wikidata.org/wiki/Q207289")

        assert found is not None
        assert found.endswith("/Nevermind")
        assert "Q207289" in http.urls[0]

    async def test_a_url_with_no_item_id_is_refused(self):
        client, http = build()

        assert await client.article_for("https://www.wikidata.org/wiki/nonsense") is None
        assert http.calls == []

    async def test_an_item_with_no_english_article_reads_as_nothing(self):
        client, _ = build(response(status=404))

        assert await client.article_for("https://www.wikidata.org/wiki/Q1") is None

    async def test_a_transport_error_reads_as_nothing(self):
        client, _ = build(httpx.ConnectError("refused"))

        assert await client.article_for("https://www.wikidata.org/wiki/Q1") is None
