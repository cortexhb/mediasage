"""Tests for the HTTP request and response models."""

import pytest
from pydantic import ValidationError

from backend.models import FilterPreviewRequest, FilterPreviewResponse, GenerateRequest


def generate(**overrides: object) -> GenerateRequest:
    """A valid generate request, with `overrides` applied.

    Validated rather than constructed: these tests feed wire-shaped input,
    including the nulls and raw dicts the form actually sends.
    """
    payload: dict[str, object] = {"prompt": "something", "genres": [], "decades": []}
    payload.update(overrides)
    return GenerateRequest.model_validate(payload)


class TestAbsentIsEmpty:
    """Absent text and answers are empty, never None.

    The form sends null for a field the user left alone, so null has to be
    accepted; it must not survive into a third state every reader checks for.
    """

    def test_a_null_prompt_reads_as_blank(self):
        assert (
            generate(prompt=None, seed_track={"rating_key": "1", "selected_dimensions": []}).prompt
            == ""
        )

    def test_a_null_note_reads_as_blank(self):
        assert generate(additional_notes=None).additional_notes == ""

    def test_null_answers_read_as_none_asked(self):
        assert generate(refinement_answers=None).refinement_answers == []

    def test_omitted_fields_are_empty_too(self):
        request = generate()

        assert (request.additional_notes, request.refinement_answers) == ("", [])

    def test_a_skipped_question_stays_none(self):
        """Inner None is a question the user passed on, not a blank answer."""
        assert generate(refinement_answers=["yes", None]).refinement_answers == ["yes", None]


class TestCheckFlow:
    """A generation needs something to work from."""

    def test_a_prompt_alone_is_enough(self):
        assert generate().prompt == "something"

    def test_a_seed_track_alone_is_enough(self):
        request = generate(
            prompt="", seed_track={"rating_key": "42", "selected_dimensions": ["mood"]}
        )

        assert request.seed_track is not None

    def test_neither_is_refused(self):
        """Without one the model would be asked to curate from nothing."""
        with pytest.raises(ValidationError, match="prompt or seed_track"):
            generate(prompt="")

    def test_a_null_prompt_and_no_seed_is_refused(self):
        """Folding null to blank must not open a way past the check."""
        with pytest.raises(ValidationError, match="prompt or seed_track"):
            generate(prompt=None)


class TestFilterPreview:
    """How much of the library a selection reaches. Counts, never costs."""

    @staticmethod
    def preview(matching: int, max_tracks_to_ai: int = 1000) -> FilterPreviewResponse:
        request = FilterPreviewRequest(max_tracks_to_ai=max_tracks_to_ai)
        return FilterPreviewResponse.of(request, matching)

    def test_caps_what_is_sent(self):
        assert self.preview(5000, max_tracks_to_ai=100).tracks_to_send == 100

    def test_no_cap_sends_everything(self):
        """A limit of zero is the user turning the cap off, not asking for none."""
        assert self.preview(5000, max_tracks_to_ai=0).tracks_to_send == 5000

    def test_under_the_cap_sends_what_there_is(self):
        assert self.preview(60, max_tracks_to_ai=100).tracks_to_send == 60

    def test_an_empty_library_sends_nothing(self):
        assert self.preview(0).tracks_to_send == 0

    def test_an_unknown_count_sends_nothing(self):
        """An unsynced cache reports -1, which is not a number of tracks."""
        assert self.preview(-1).tracks_to_send == 0

    def test_the_matching_count_is_reported_as_given(self):
        assert self.preview(5000, max_tracks_to_ai=100).matching_tracks == 5000

    def test_nothing_is_predicted_about_cost(self):
        """Tokens are counted by the provider, after the call, or not at all."""
        fields = set(FilterPreviewResponse.model_fields)

        assert fields == {"matching_tracks", "tracks_to_send"}
