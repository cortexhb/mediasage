"""Tests for what a run is predicted to cost."""

from backend.api import estimates
from backend.models import FilterPreviewRequest
from tests.api.conftest import mediasage_config

PRICED = mediasage_config().model_copy(update={"llm": mediasage_config().llm.model_copy(
    update={
        "cost_analysis_input": 3.0,
        "cost_analysis_output": 15.0,
        "cost_generation_input": 1.0,
        "cost_generation_output": 5.0,
    }
)})


def request(**overrides) -> FilterPreviewRequest:
    fields = {"track_count": 25, "max_tracks_to_ai": 1000}
    fields.update(overrides)
    return FilterPreviewRequest(**fields)


class TestPlaylist:
    def test_caps_what_is_sent(self):
        estimate = estimates.FilterPreviewResponse.of(request(max_tracks_to_ai=100), 5000, PRICED)
        assert estimate.tracks_to_send == 100

    def test_no_cap_sends_everything(self):
        """A limit of zero is the user turning the cap off, not asking for none."""
        estimate = estimates.FilterPreviewResponse.of(request(max_tracks_to_ai=0), 5000, PRICED)
        assert estimate.tracks_to_send == 5000

    def test_an_empty_library_sends_nothing(self):
        estimate = estimates.FilterPreviewResponse.of(request(), 0, PRICED)
        assert estimate.tracks_to_send == 0
        assert estimate.estimated_input_tokens == estimates.PLAYLIST_ANALYSIS_INPUT

    def test_input_grows_with_the_tracks_sent(self):
        small = estimates.FilterPreviewResponse.of(request(), 100, PRICED)
        large = estimates.FilterPreviewResponse.of(request(), 200, PRICED)
        assert large.estimated_input_tokens - small.estimated_input_tokens == (
            100 * PRICED.budget.tokens_per_track
        )

    def test_output_grows_with_the_playlist_length(self):
        short = estimates.FilterPreviewResponse.of(request(track_count=10), 100, PRICED)
        long = estimates.FilterPreviewResponse.of(request(track_count=50), 100, PRICED)
        assert long.estimated_output_tokens > short.estimated_output_tokens

    def test_an_unpriced_provider_reports_no_cost(self):
        """An unset price means no cost shown rather than a wrong one."""
        assert estimates.FilterPreviewResponse.of(request(), 500, mediasage_config()).estimated_cost == 0.0

    def test_a_priced_provider_reports_one(self):
        assert estimates.FilterPreviewResponse.of(request(), 500, PRICED).estimated_cost > 0


class TestAlbums:
    def test_caps_what_is_sent(self):
        assert estimates.AlbumPreviewResponse.of(5000, 2500, PRICED).albums_to_send == 2500

    def test_no_cap_sends_everything(self):
        assert estimates.AlbumPreviewResponse.of(5000, 0, PRICED).albums_to_send == 5000

    def test_an_empty_library_sends_nothing(self):
        estimate = estimates.AlbumPreviewResponse.of(0, 2500, PRICED)
        assert estimate.albums_to_send == 0
        assert estimate.matching_albums == 0

    def test_input_grows_with_the_configured_album_size(self):
        estimate = estimates.AlbumPreviewResponse.of(100, 0, PRICED)
        expected = (
            estimates.ALBUM_ANALYSIS_INPUT
            + estimates.ALBUM_GENERATION_INPUT
            + 100 * PRICED.budget.tokens_per_album
        )
        assert estimate.estimated_input_tokens == expected

    def test_an_unpriced_provider_reports_no_cost(self):
        assert estimates.AlbumPreviewResponse.of(100, 0, mediasage_config()).estimated_cost == 0.0
