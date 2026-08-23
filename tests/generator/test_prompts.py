"""Tests for the words playlist generation sends a model."""

from backend.generator import prompts
from backend.models import Track


def track(
    title: str = "Fake Plastic Trees",
    artist: str = "Radiohead",
    album: str = "The Bends",
    duration_ms: int = 290000,
    year: int | None = 1995,
) -> Track:
    """One library track; the rating key follows the title so it stays unique."""
    return Track(
        rating_key=title,
        title=title,
        artist=artist,
        album=album,
        duration_ms=duration_ms,
        year=year,
    )


def picked(**overrides: object) -> dict:
    """One selection as the model returns it."""
    fields: dict[str, object] = {
        "artist": "Radiohead",
        "title": "Fake Plastic Trees",
        "album": "The Bends",
        "reason": "It aches",
    }
    fields.update(overrides)
    return fields


class TestSelection:
    def test_the_library_is_numbered_from_one(self):
        """The model refers to tracks by name, but the numbering keeps it honest."""
        sent = prompts.selection([track("A"), track("B")], 2)

        assert "1. Radiohead - A" in sent
        assert "2. Radiohead - B" in sent

    def test_a_track_with_no_year_says_so(self):
        assert "Unknown year" in prompts.selection([track(year=None)], 1)

    def test_the_count_is_asked_for(self):
        assert "Select 25 tracks" in prompts.selection([track()], 25)

    def test_the_request_comes_before_the_library(self):
        """A model reads the ask before it reads the catalogue."""
        sent = prompts.selection([track()], 1, prompt="something atmospheric")

        assert sent.index("something atmospheric") < sent.index("Select 1 tracks")

    def test_a_seed_track_is_described(self):
        sent = prompts.selection([track()], 1, seed_track=track("Black", artist="Pearl Jam"))

        assert "Seed track: Black by Pearl Jam" in sent

    def test_dimensions_are_only_sent_with_a_seed(self):
        """They name what to explore about the seed, so alone they mean nothing."""
        sent = prompts.selection([track()], 1, selected_dimensions=["mood"])

        assert "Explore these dimensions" not in sent

    def test_dimensions_ride_with_their_seed(self):
        sent = prompts.selection(
            [track()], 1, seed_track=track(), selected_dimensions=["mood", "era"]
        )

        assert "Explore these dimensions: mood, era" in sent

    def test_notes_reach_the_model(self):
        assert "no live cuts" in prompts.selection([track()], 1, additional_notes="no live cuts")

    def test_answered_refinements_are_joined(self):
        sent = prompts.selection([track()], 1, refinement_answers=["slower", "older"])

        assert "User preferences: slower, older" in sent

    def test_unanswered_refinements_are_dropped(self):
        """A blank answer is no preference, not an empty one."""
        sent = prompts.selection([track()], 1, refinement_answers=[None, "", "slower"])

        assert "User preferences: slower" in sent

    def test_all_refinements_blank_says_nothing(self):
        sent = prompts.selection([track()], 1, refinement_answers=[None, ""])

        assert "User preferences" not in sent

    def test_a_bare_request_is_just_the_library(self):
        sent = prompts.selection([track()], 1)

        assert sent.startswith("\nSelect 1 tracks")


class TestNarrative:
    def test_each_pick_carries_its_reason(self):
        sent = prompts.narrative([picked()])

        assert 'Radiohead - "Fake Plastic Trees": It aches' in sent

    def test_a_pick_with_no_reason_key_gets_a_stand_in(self):
        fields = picked()
        del fields["reason"]

        assert "Selected for this playlist" in prompts.narrative([fields])

    def test_an_empty_reason_is_sent_empty(self):
        """The stand-in is a `dict.get` default, so only a missing key reaches it."""
        sent = prompts.narrative([picked(reason="")])

        assert sent.endswith('"Fake Plastic Trees": ')

    def test_a_pick_missing_its_names_still_renders(self):
        assert "Unknown" in prompts.narrative([{}])

    def test_the_request_is_included_when_there_is_one(self):
        sent = prompts.narrative([picked()], "something for the drive home")

        assert sent.startswith("User's request: something for the drive home")

    def test_no_request_starts_at_the_tracks(self):
        assert prompts.narrative([picked()]).startswith("Selected tracks:")

    def test_the_list_is_capped(self):
        """A whole playlist is context spent on a three-sentence answer."""
        many = [picked(title=f"Track{i}") for i in range(prompts.NARRATIVE_TRACK_LIMIT + 5)]

        sent = prompts.narrative(many)

        assert f"Track{prompts.NARRATIVE_TRACK_LIMIT - 1}" in sent
        assert f"Track{prompts.NARRATIVE_TRACK_LIMIT}" not in sent
