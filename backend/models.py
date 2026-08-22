"""Pydantic models for MediaSage API contracts and internal data structures."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.config.models import DefaultsConfig
from backend.library import DecadeCount, GenreCount, SyncProgress
from backend.recommender import (
    ClarifyingQuestion,
)

# =============================================================================
# Core Entities
# =============================================================================


class Track(BaseModel):
    """A music track from the Plex library."""

    rating_key: str
    title: str
    artist: str
    album: str
    duration_ms: int
    year: int | None = None
    genres: list[str] = []
    art_url: str | None = None

    @property
    def duration_formatted(self) -> str:
        """Return duration as M:SS format."""
        minutes = self.duration_ms // 60000
        seconds = (self.duration_ms % 60000) // 1000
        return f"{minutes}:{seconds:02d}"


class Dimension(BaseModel):
    """A musical dimension identified from a seed track."""

    id: str
    label: str
    description: str


class FilterSet(BaseModel):
    """Filters applied to narrow track selection."""

    genres: list[str] = []
    decades: list[str] = []
    track_count: int = 25
    exclude_live: bool = True

    @field_validator("track_count")
    @classmethod
    def validate_track_count(cls, v: int) -> int:
        if v not in [15, 25, 50, 100]:
            raise ValueError("track_count must be 15, 25, 50, or 100")
        return v


class Playlist(BaseModel):
    """A generated playlist with tracks and metadata."""

    name: str
    tracks: list[Track]
    source_prompt: str | None = None
    seed_track_key: str | None = None
    selected_dimensions: list[str] | None = None

    @property
    def duration_total(self) -> int:
        """Total duration in milliseconds."""
        return sum(t.duration_ms for t in self.tracks)

    @property
    def track_count(self) -> int:
        return len(self.tracks)


# =============================================================================
# API Request/Response Models
# =============================================================================


class LibraryStatsResponse(BaseModel):
    """Library statistics response."""

    total_tracks: int
    genres: list[GenreCount]
    decades: list[DecadeCount]


class AnalyzePromptRequest(BaseModel):
    """Request to analyze a natural language prompt."""

    prompt: str = Field(..., min_length=1, max_length=2000)


class AnalyzePromptResponse(BaseModel):
    """Response from prompt analysis."""

    suggested_genres: list[str]
    suggested_decades: list[str]
    available_genres: list[GenreCount]
    available_decades: list[DecadeCount]
    reasoning: str
    token_count: int = 0
    estimated_cost: float = 0.0


class AnalyzeTrackRequest(BaseModel):
    """Request to analyze a seed track for dimensions."""

    rating_key: str


class AnalyzeTrackResponse(BaseModel):
    """Response from track analysis."""

    track: Track
    dimensions: list[Dimension]
    token_count: int = 0
    estimated_cost: float = 0.0


class FilterPreviewRequest(BaseModel):
    """Request to preview filter results."""

    genres: list[str] = []
    decades: list[str] = []
    track_count: int = 25
    max_tracks_to_ai: int = 500  # 0 = no limit
    min_rating: int = 0  # 0 = any, 2/4/6/8/10 = minimum rating (Plex uses 0-10)
    exclude_live: bool = True


class FilterPreviewResponse(BaseModel):
    """Response with filter preview stats."""

    matching_tracks: int  # -1 if unknown
    tracks_to_send: int  # How many will actually be sent to AI
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost: float


class SeedTrackInput(BaseModel):
    """Seed track input for generation."""

    rating_key: str
    selected_dimensions: list[str]


class GenerateRequest(BaseModel):
    """Request to generate a playlist."""

    prompt: str | None = None
    seed_track: SeedTrackInput | None = None
    additional_notes: str | None = None
    refinement_answers: list[str | None] | None = None
    genres: list[str]
    decades: list[str]
    track_count: int = 25
    exclude_live: bool = True
    min_rating: int = 0  # 0 = any, 2/4/6/8/10 = minimum rating
    max_tracks_to_ai: int = 500  # 0 = no limit

    @model_validator(mode="after")
    def check_flow(self) -> GenerateRequest:
        if not self.prompt and not self.seed_track:
            raise ValueError("Either prompt or seed_track must be provided")
        return self


class GenerateResponse(BaseModel):
    """Response from playlist generation."""

    tracks: list[Track]
    token_count: int
    estimated_cost: float
    # Curator narrative fields
    playlist_title: str = ""
    narrative: str = ""
    track_reasons: dict[str, str] = {}


def _validate_rating_keys(v: list[str]) -> list[str]:
    """Validate a list of Plex rating keys (must be non-empty, all numeric)."""
    if not v:
        raise ValueError("At least one track is required")
    for key in v:
        if not key.isdigit():
            raise ValueError(f"Invalid rating key: {key}")
    return v


def _truncate_description(v: str) -> str:
    """Truncate description to 2000 chars for Plex compatibility."""
    return v[:2000] if v else v


class SavePlaylistRequest(BaseModel):
    """Request to save a playlist to Plex."""

    name: str
    rating_keys: list[str]
    description: str = ""  # Playlist description (narrative) saved to Plex

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Playlist name cannot be empty")
        return v.strip()

    @field_validator("description")
    @classmethod
    def truncate_description(cls, v: str) -> str:
        return _truncate_description(v)

    @field_validator("rating_keys")
    @classmethod
    def validate_rating_keys(cls, v: list[str]) -> list[str]:
        return _validate_rating_keys(v)


# =============================================================================
# Instant Queue Models (005)
# =============================================================================


class UpdatePlaylistRequest(BaseModel):
    """Request to update an existing playlist."""

    playlist_id: str
    rating_keys: list[str]
    mode: Literal["replace", "append"]
    description: str = ""

    @field_validator("description")
    @classmethod
    def truncate_description(cls, v: str) -> str:
        return _truncate_description(v)

    @field_validator("playlist_id")
    @classmethod
    def validate_playlist_id(cls, v: str) -> str:
        if v != "__scratch__" and not v.isdigit():
            raise ValueError("playlist_id must be '__scratch__' or a numeric rating key")
        return v

    @field_validator("rating_keys")
    @classmethod
    def validate_rating_keys(cls, v: list[str]) -> list[str]:
        return _validate_rating_keys(v)


class PlayQueueRequest(BaseModel):
    """Request to create a play queue."""

    rating_keys: list[str]
    client_id: str
    mode: Literal["replace", "play_next"] = "replace"

    @field_validator("client_id")
    @classmethod
    def validate_client_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("client_id cannot be empty")
        return v

    @field_validator("rating_keys")
    @classmethod
    def validate_rating_keys(cls, v: list[str]) -> list[str]:
        return _validate_rating_keys(v)


class ConfigResponse(BaseModel):
    """Config without secrets for display."""

    version: str
    plex_url: str
    plex_connected: bool
    plex_token_set: bool  # True if token is configured (without revealing it)
    music_library: str | None
    llm_provider: str
    llm_configured: bool
    llm_api_key_set: bool  # True if API key is configured (without revealing it)
    model_analysis: str  # The analysis model being used
    model_generation: str  # The generation model being used
    max_tracks_to_ai: int  # Recommended max tracks for this model
    max_albums_to_ai: int  # Recommended max albums for this model
    # Per million tokens, as configured; 0.0 throughout means unpriced.
    cost_generation_input: float = 0.0
    cost_generation_output: float = 0.0
    cost_analysis_input: float = 0.0
    cost_analysis_output: float = 0.0
    is_priced: bool = False
    defaults: DefaultsConfig
    # Local provider fields
    endpoint_url: str = ""
    context_window: int
    is_local_provider: bool = False
    provider_from_env: bool = False  # True if LLM_PROVIDER env var is overriding UI


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    plex_connected: bool
    llm_configured: bool


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: str | None = None


# =============================================================================
# Library Cache Models
# =============================================================================


class LibraryCacheStatusResponse(BaseModel):
    """Response from GET /api/library/status."""

    track_count: int
    synced_at: str | None = None
    is_syncing: bool
    sync_progress: SyncProgress | None = None
    error: str | None = None
    plex_connected: bool


class SyncTriggerResponse(BaseModel):
    """Response from POST /api/library/sync."""

    started: bool
    blocking: bool = False


# =============================================================================
# Recommendation Models (006)
# =============================================================================


class AnalyzePromptFiltersRequest(BaseModel):
    """Request to analyze a prompt and suggest genre/decade filters."""

    prompt: str
    genres: list[str] = []
    decades: list[str] = []


class AnalyzePromptFiltersResponse(BaseModel):
    """Response with suggested genre/decade pre-selections."""

    genres: list[str] = []
    decades: list[str] = []
    reasoning: str = ""


class RecommendQuestionsRequest(BaseModel):
    """Request to generate clarifying questions."""

    prompt: str = Field(..., min_length=1, max_length=2000)


class RecommendQuestionsResponse(BaseModel):
    """Response with clarifying questions."""

    questions: list[ClarifyingQuestion]
    session_id: str
    token_count: int = 0
    estimated_cost: float = 0.0


class RecommendSwitchModeRequest(BaseModel):
    """Request to switch a recommendation session to a different mode."""

    session_id: str
    mode: Literal["library", "discovery"]


class RecommendSwitchModeResponse(BaseModel):
    """Response after switching recommendation mode."""

    session_id: str


class RecommendGenerateRequest(BaseModel):
    """Request to generate album recommendations."""

    session_id: str
    answers: list[str | None]
    answer_texts: list[str] = []
    mode: Literal["library", "discovery"] = "library"
    genres: list[str] = []
    decades: list[str] = []
    familiarity_pref: Literal["any", "comfort", "rediscover", "hidden_gems"] = "any"
    max_albums: int = 2500

    @field_validator("max_albums")
    @classmethod
    def validate_max_albums(cls, v: int) -> int:
        if v < 0:
            raise ValueError("max_albums must be non-negative")
        return min(v, 50000)


class AlbumPreviewResponse(BaseModel):
    """Response from album preview endpoint."""

    matching_albums: int
    albums_to_send: int
    estimated_input_tokens: int = 0
    estimated_cost: float = 0.0


# =============================================================================
# Results Persistence Models
# =============================================================================


# =============================================================================
# Setup/Onboarding Models
# =============================================================================


class SetupStatusResponse(BaseModel):
    """Full onboarding checklist state."""

    data_dir_writable: bool
    process_uid: int = 0
    process_gid: int = 0
    data_dir: str = ""
    plex_connected: bool
    plex_error: str | None = None
    plex_from_env: bool = False
    music_libraries: list[str] = []
    llm_configured: bool
    llm_provider: str = ""
    llm_from_env: bool = False
    library_synced: bool
    track_count: int = 0
    is_syncing: bool = False
    sync_progress: SyncProgress | None = None
    setup_complete: bool


class ValidatePlexRequest(BaseModel):
    """Request to validate Plex credentials during setup."""

    plex_url: str
    plex_token: str
    music_library: str = "Music"


class ValidatePlexResponse(BaseModel):
    """Response from Plex validation."""

    success: bool
    error: str | None = None
    server_name: str | None = None
    music_libraries: list[str] = []


class ValidateAIRequest(BaseModel):
    """Request to validate AI provider credentials during setup."""

    provider: str
    api_key: str = ""
    endpoint_url: str = ""
    # Needed to build a client at all: the probe is a real one-token completion.
    model: str = ""
    context_window: int = 0


class ValidateAIResponse(BaseModel):
    """Response from AI provider validation."""

    success: bool
    error: str | None = None
    provider_name: str = ""


class SetupCompleteResponse(BaseModel):
    """Response from marking setup as complete."""

    success: bool
