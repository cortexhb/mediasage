"""What a run will cost, before it is paid for.

Each preview response knows how to estimate itself from the filters and the
configuration, so an endpoint hands over what it counted and returns the model.
Entry points: `FilterPreviewResponse.of`, `AlbumPreviewResponse.of`.

Both preview endpoints answer the same question -- how many tokens and how
many dollars -- from measured prompt sizes rather than from a live call. The
numbers below were measured against real runs; they move when a prompt is
rewritten, which is why each is named and commented rather than inlined.

Per-track and per-album prompt sizes are the user's own tunables and are read
off `BudgetConfig`: they depend on how long the names in a library are. The
per-call figures below are not: they are the size of prompts this repository
ships, so they move with a prompt rewrite rather than with a deployment.
"""

from typing import Final, Self

from pydantic import BaseModel

from backend.config import MediasageConfig
from backend.models import FilterPreviewRequest

# --- Playlist generation: analysis, generation, narrative ---------------

# Prompt analysis (700) plus the closing narrative (400), both on the analysis
# model. Neither grows with the library.
PLAYLIST_ANALYSIS_INPUT: Final = 1100

# What those two calls write back: the analysis (100) and the narrative (200).
PLAYLIST_ANALYSIS_OUTPUT: Final = 300

# Tokens the model writes back per track it picks.
PLAYLIST_TOKENS_PER_PICK: Final = 60

# --- Album recommendation: up to seven calls ---------------------------

# Gap analysis (800), pitch writing (1500), validation (2000) and the rewrite
# (1500) all run on the analysis model. The last two only happen when there is
# research to check against, so this is the ceiling rather than the average.
ALBUM_ANALYSIS_INPUT: Final = 800 + 1500 + 2000 + 1500

# What those four write back.
ALBUM_ANALYSIS_OUTPUT: Final = 50 + 800 + 200 + 800

# Question generation (600), the selection preamble (400) and fact extraction
# (2000), on the generation model. The album list is added per album.
ALBUM_GENERATION_INPUT: Final = 600 + 400 + 2000

# What those three write back.
ALBUM_GENERATION_OUTPUT: Final = 200 + 300 + 500



class Preview(BaseModel):
    """What one run will send to a model, and what that will cost."""

    @staticmethod
    def capped(available: int, limit: int) -> int:
        """How many rows are actually sent; a limit of zero means all of them."""
        if available <= 0:
            return 0
        return min(available, limit) if limit > 0 else available


class FilterPreviewResponse(Preview):
    """What one playlist generation will send, and what it will cost."""

    # -1 when the count is unknown, which is what an unsynced cache reports.
    matching_tracks: int
    tracks_to_send: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost: float

    @classmethod
    def of(
        cls, request: FilterPreviewRequest, matching_tracks: int, config: MediasageConfig
    ) -> Self:
        """Estimate one generation over `matching_tracks` of the library."""
        tracks_to_send = cls.capped(matching_tracks, request.max_tracks_to_ai)

        generation_input = tracks_to_send * config.budget.tokens_per_track
        generation_output = request.track_count * PLAYLIST_TOKENS_PER_PICK

        return cls(
            matching_tracks=matching_tracks,
            tracks_to_send=tracks_to_send,
            estimated_input_tokens=PLAYLIST_ANALYSIS_INPUT + generation_input,
            estimated_output_tokens=PLAYLIST_ANALYSIS_OUTPUT + generation_output,
            estimated_cost=(
                config.llm.estimate_cost(
                    "analysis", PLAYLIST_ANALYSIS_INPUT, PLAYLIST_ANALYSIS_OUTPUT
                )
                + config.llm.estimate_cost("generation", generation_input, generation_output)
            ),
        )


class AlbumPreviewResponse(Preview):
    """What one recommendation round will send, and what it will cost."""

    matching_albums: int
    albums_to_send: int
    estimated_input_tokens: int = 0
    estimated_cost: float = 0.0

    @classmethod
    def of(cls, matching_albums: int, max_albums: int, config: MediasageConfig) -> Self:
        """Estimate one round over `matching_albums` of the library."""
        albums_to_send = cls.capped(matching_albums, max_albums)

        generation_input = (
            ALBUM_GENERATION_INPUT + albums_to_send * config.budget.tokens_per_album
        )

        return cls(
            matching_albums=matching_albums,
            albums_to_send=albums_to_send,
            estimated_input_tokens=ALBUM_ANALYSIS_INPUT + generation_input,
            estimated_cost=(
                config.llm.estimate_cost(
                    "analysis", ALBUM_ANALYSIS_INPUT, ALBUM_ANALYSIS_OUTPUT
                )
                + config.llm.estimate_cost(
                    "generation", generation_input, ALBUM_GENERATION_OUTPUT
                )
            ),
        )
