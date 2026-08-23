"""Tests for the shapes the research APIs answer with."""

from backend.config import ResearchConfig
from backend.research.models import ReleaseDetail, ReleaseGroup, ReleaseGroupMatch


def relation(kind: str, url: str) -> dict:
    """One MusicBrainz url-rel, shaped the way the API nests it."""
    return {"type": kind, "url": {"resource": url}}


class TestReleaseGroupMatch:
    def test_reads_the_fields_a_score_needs(self):
        match = ReleaseGroupMatch.of(
            {
                "id": "mbid-1",
                "title": "Nevermind",
                "score": 100,
                "primary-type": "Album",
                "first-release-date": "1991-09-24",
                "artist-credit": [{"name": "Nirvana"}],
            }
        )

        assert match.mbid == "mbid-1"
        assert match.title == "Nevermind"
        assert match.first_release_date == "1991-09-24"

    def test_an_exact_artist_and_title_outscores_a_partial(self):
        exact = ReleaseGroupMatch.of(
            {
                "id": "a",
                "title": "Nevermind",
                "artist-credit": [{"name": "Nirvana"}],
            }
        )
        partial = ReleaseGroupMatch.of(
            {
                "id": "b",
                "title": "Nevermind Live",
                "artist-credit": [{"name": "Someone Else"}],
            }
        )

        assert exact.score("Nevermind", None, "Nirvana") > partial.score(
            "Nevermind", None, "Nirvana"
        )

    def test_a_matching_year_lifts_the_score(self):
        dated = ReleaseGroupMatch.of(
            {
                "id": "a",
                "title": "Ten",
                "first-release-date": "1991-08-27",
            }
        )
        undated = ReleaseGroupMatch.of({"id": "b", "title": "Ten"})

        assert dated.score("Ten", 1991, "Pearl Jam") > undated.score("Ten", 1991, "Pearl Jam")


class TestReleaseGroup:
    def test_reads_each_relation_into_its_own_field(self, research_config):
        group = ReleaseGroup.of(
            {
                "relations": [
                    relation("wikipedia", "https://en.wikipedia.org/wiki/Nevermind"),
                    relation("wikidata", "https://www.wikidata.org/wiki/Q207289"),
                    relation("discogs", "https://www.discogs.com/master/11557"),
                    relation("review", "https://pitchfork.com/reviews/albums/1"),
                ],
            },
            research_config,
        )

        assert group.wikipedia_url.endswith("/Nevermind")
        assert group.wikidata_url.endswith("/Q207289")
        assert group.discogs_url.endswith("/11557")
        assert group.review_urls == ["https://pitchfork.com/reviews/albums/1"]

    def test_drops_a_blocked_review_host(self, research_config):
        """AllMusic's terms prohibit automated access, so its URL never lands."""
        group = ReleaseGroup.of(
            {
                "relations": [
                    relation("review", "https://www.allmusic.com/album/x"),
                    relation("review", "https://pitchfork.com/reviews/albums/1"),
                ],
            },
            research_config,
        )

        assert group.review_urls == ["https://pitchfork.com/reviews/albums/1"]

    def test_the_blocked_list_is_configurable(self):
        config = ResearchConfig(blocked_review_hosts=["pitchfork.com"])
        group = ReleaseGroup.of(
            {
                "relations": [
                    relation("review", "https://www.allmusic.com/album/x"),
                    relation("review", "https://pitchfork.com/reviews/albums/1"),
                ],
            },
            config,
        )

        assert group.review_urls == ["https://www.allmusic.com/album/x"]

    def test_caps_the_reviews_at_the_configured_count(self):
        config = ResearchConfig(max_reviews=1)
        group = ReleaseGroup.of(
            {
                "relations": [
                    relation("review", "https://a.test/1"),
                    relation("review", "https://b.test/2"),
                ],
            },
            config,
        )

        assert group.review_urls == ["https://a.test/1"]

    def test_picks_the_earliest_release(self, research_config):
        """The earliest carries the original listing; a later one carries bonus tracks."""
        group = ReleaseGroup.of(
            {
                "releases": [
                    {"id": "reissue", "date": "2011-09-20"},
                    {"id": "original", "date": "1991-09-24"},
                ],
            },
            research_config,
        )

        assert group.earliest_release_mbid == "original"
        assert group.release_date == "1991-09-24"

    def test_an_undated_release_sorts_last(self, research_config):
        group = ReleaseGroup.of(
            {
                "releases": [{"id": "undated"}, {"id": "dated", "date": "1991-09-24"}],
            },
            research_config,
        )

        assert group.earliest_release_mbid == "dated"

    def test_an_empty_payload_yields_empty_fields(self, research_config):
        group = ReleaseGroup.of({}, research_config)

        assert group.review_urls == []
        assert group.earliest_release_mbid == ""

    def test_a_relation_without_a_url_is_skipped(self, research_config):
        group = ReleaseGroup.of({"relations": [{"type": "review", "url": {}}]}, research_config)

        assert group.review_urls == []


class TestReleaseDetail:
    def test_reads_the_track_listing_in_order(self):
        detail = ReleaseDetail.of(
            {
                "media": [
                    {
                        "tracks": [
                            {"title": "Smells Like Teen Spirit"},
                            {"title": "In Bloom"},
                        ]
                    }
                ],
            }
        )

        assert detail.track_listing == ["Smells Like Teen Spirit", "In Bloom"]

    def test_reads_the_label(self):
        detail = ReleaseDetail.of({"label-info": [{"label": {"name": "DGC"}}]})

        assert detail.label == "DGC"

    def test_an_empty_payload_yields_empty_fields(self):
        detail = ReleaseDetail.of({})

        assert detail.track_listing == []
        assert detail.label == ""
