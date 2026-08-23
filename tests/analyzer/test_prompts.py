"""Tests for the words the analyzer sends a model."""

from backend.analyzer import prompts
from backend.library import DecadeCount, GenreCount
from backend.models import LibraryStatsResponse, Track


def library(
    genres: list[GenreCount] | None = None, decades: list[DecadeCount] | None = None
) -> LibraryStatsResponse:
    """What Plex reports the library holds."""
    return LibraryStatsResponse(
        total_tracks=300,
        genres=genres
        if genres is not None
        else [
            GenreCount(name="Alternative", count=100),
            GenreCount(name="Rock", count=200),
        ],
        decades=decades if decades is not None else [DecadeCount(name="1990s", count=150)],
    )


class TestFilters:
    def test_the_request_is_quoted_back(self):
        assert '"90s rock"' in prompts.filters("90s rock", library())

    def test_a_genre_carries_its_count(self):
        """The count is how the model tells a real genre from a stray tag."""
        sent = prompts.filters("test", library())

        assert "Alternative (100)" in sent
        assert "1990s (150)" in sent

    def test_an_uncounted_genre_is_named_alone(self):
        sent = prompts.filters("test", library(genres=[GenreCount(name="Rock")]))

        assert "Rock" in sent
        assert "Rock (" not in sent

    def test_the_genre_list_is_capped(self):
        """A large library's whole tag list is tokens spent on nothing."""
        many = [GenreCount(name=f"Genre{i}", count=i + 1) for i in range(prompts.GENRE_LIMIT + 5)]

        sent = prompts.filters("test", library(genres=many))

        assert f"Genre{prompts.GENRE_LIMIT - 1}" in sent
        assert f"Genre{prompts.GENRE_LIMIT}" not in sent

    def test_every_decade_is_listed(self):
        """Decades are a handful at most, so there is nothing to cap."""
        decades = [DecadeCount(name=f"{1900 + i * 10}s", count=1) for i in range(12)]

        assert "2010s" in prompts.filters("test", library(decades=decades))

    def test_an_empty_library_still_renders(self):
        """Plex answers this before the first sync finishes."""
        sent = prompts.filters("test", library(genres=[], decades=[]))

        assert "Available genres in their library:" in sent


class TestTrack:
    def test_every_field_reaches_the_prompt(self):
        sent = prompts.track(
            Track(
                rating_key="1",
                title="Fake Plastic Trees",
                artist="Radiohead",
                album="The Bends",
                duration_ms=290000,
                year=1995,
                genres=["Alternative", "Rock"],
            )
        )

        assert "Fake Plastic Trees" in sent
        assert "Radiohead" in sent
        assert "The Bends" in sent
        assert "Year: 1995" in sent
        assert "Genres: Alternative, Rock" in sent

    def test_a_track_with_nothing_known_says_unknown(self):
        """Plex leaves both blank often enough that the prompt must read."""
        sent = prompts.track(
            Track(rating_key="2", title="Untitled", artist="Someone", album="", duration_ms=1)
        )

        assert "Year: Unknown" in sent
        assert "Genres: Unknown" in sent
