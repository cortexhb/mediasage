"""Pydantic models for MediaSage API contracts and internal data structures."""

import os
from typing import Annotated, Any, Final, Literal, Self

from pydantic import BaseModel, Field, SecretStr, TypeAdapter, field_validator, model_validator

from backend.config.models import PROVIDER_LABELS, DefaultsConfig
from backend.config.settings import MediasageConfig
from backend.library import DecadeCount, GenreCount, SyncProgress, TrackRecord
from backend.llm.models import TokenBudget
from backend.recommender import (
    ClarifyingQuestion,
    RecommendGenerateResponse,
)
from backend.results import ResultFields
from backend.sse import ErrorFrame, ProgressFrame
from backend.version import Version

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

    @classmethod
    def of_cached(cls, cached: TrackRecord) -> Self:
        """Build from a row of the local library cache.

        The cache holds no art URL: art is proxied under the rating key, so it
        is derived rather than stored.
        """
        return cls(
            rating_key=cached.rating_key,
            title=cached.title,
            artist=cached.artist,
            album=cached.album,
            duration_ms=cached.duration_ms,
            year=cached.year,
            genres=cached.genres,
            art_url=f"/api/art/{cached.rating_key}",
        )

    @classmethod
    def of_plex(cls, plex_track: Any) -> Self:
        """Build from a raw Plex track, as a listing hands one back.

        Year is read off the album first: Plex stores it there, and a track
        carries one only when it was tagged individually.
        """
        genres = [
            genre.tag if hasattr(genre, "tag") else str(genre)
            for genre in getattr(plex_track, "genres", None) or []
        ]

        return cls(
            rating_key=str(plex_track.ratingKey),
            title=plex_track.title,
            artist=plex_track.grandparentTitle or "Unknown Artist",
            album=plex_track.parentTitle or "Unknown Album",
            duration_ms=plex_track.duration or 0,
            year=getattr(plex_track, "parentYear", None) or getattr(plex_track, "year", None),
            # Art is proxied so the Plex token never reaches the browser.
            art_url=f"/api/art/{plex_track.ratingKey}" if plex_track.ratingKey else None,
            genres=genres,
        )

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


class SeedTrackInput(BaseModel):
    """Seed track input for generation."""

    rating_key: str
    selected_dimensions: list[str]


class GenerateRequest(BaseModel):
    """Request to generate a playlist.

    Absent text and answers are empty, never None: "" and [] already mean
    absent, and a third state only buys every reader an `or ""`. The form
    still sends null for a field left alone, so null is folded on the way in.
    """

    prompt: str = ""
    seed_track: SeedTrackInput | None = None
    additional_notes: str = ""
    # Inner None is a skipped question, not a blank answer.
    refinement_answers: list[str | None] = []
    genres: list[str]
    decades: list[str]
    track_count: int = 25
    exclude_live: bool = True
    min_rating: int = 0  # 0 = any, 2/4/6/8/10 = minimum rating
    max_tracks_to_ai: int = 500  # 0 = no limit

    @field_validator("prompt", "additional_notes", mode="before")
    @classmethod
    def blank_for_null(cls, v: Any) -> Any:
        """The form sends null for a text field the user left alone."""
        return "" if v is None else v

    @field_validator("refinement_answers", mode="before")
    @classmethod
    def nothing_for_null(cls, v: Any) -> Any:
        """The form sends null when it asked no refinement questions."""
        return [] if v is None else v

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


# =============================================================================
# Stream Frames
# =============================================================================
#
# Untagged unions: the SSE event name is the discriminant, and it
# travels outside the JSON payload rather than in it.


class NarrativeFrame(BaseModel):
    """The curator's writing, sent before the tracks it describes."""

    playlist_title: str
    narrative: str
    track_reasons: dict[str, str]
    user_request: str


class TracksFrame(BaseModel):
    """One batch of matched tracks, and where it starts in the playlist."""

    batch: list[Track]
    index: int


class PlaylistCompleteFrame(BaseModel):
    """The run's totals. Metadata only: the tracks already went out in batches."""

    track_count: int
    token_count: int
    estimated_cost: float
    playlist_title: str
    narrative: str
    track_reasons: dict[str, str]
    # Absent when history could not be written; the playlist is still valid.
    result_id: str | None = None


PlaylistStreamFrame = (
    ProgressFrame | NarrativeFrame | TracksFrame | PlaylistCompleteFrame | ErrorFrame
)


class RecommendResultFrame(RecommendGenerateResponse):
    """The finished round, and where it was saved."""

    result_id: str | None = None


RecommendStreamFrame = ProgressFrame | RecommendResultFrame | ErrorFrame


# =============================================================================
# Saved Results
# =============================================================================


class PlaylistResultDetail(ResultFields):
    """A saved playlist, with the response the history page re-renders it from."""

    type: Literal["prompt_playlist", "seed_playlist"]
    snapshot: GenerateResponse


class AlbumResultDetail(ResultFields):
    """A saved recommendation round, with the response it re-renders from."""

    type: Literal["album_recommendation"]
    snapshot: RecommendGenerateResponse


# Not in `backend.results`: both snapshot shapes import that package.
ResultDetail = Annotated[PlaylistResultDetail | AlbumResultDetail, Field(discriminator="type")]

RESULT_DETAIL_ADAPTER: TypeAdapter[PlaylistResultDetail | AlbumResultDetail] = TypeAdapter(
    ResultDetail
)


# Plex stores no more of a playlist summary than this.
DESCRIPTION_LIMIT: Final = 2000


class TrackListRequest(BaseModel):
    """A request naming tracks by Plex rating key.

    A mixin rather than a base carrying the field: the requests below are
    written in their own field order, and inheriting one would move it.
    """

    @field_validator("rating_keys", check_fields=False)
    @classmethod
    def validate_rating_keys(cls, v: list[str]) -> list[str]:
        """Every key must be present and numeric; Plex 404s on anything else."""
        if not v:
            raise ValueError("At least one track is required")
        for key in v:
            if not key.isdigit():
                raise ValueError(f"Invalid rating key: {key}")
        return v


class DescribedRequest(BaseModel):
    """A request carrying a playlist description Plex will store.

    A mixin for the same reason as `TrackListRequest`.
    """

    @field_validator("description", check_fields=False)
    @classmethod
    def truncate_description(cls, v: str) -> str:
        """Trim rather than reject: a long narrative is still a good playlist."""
        return v[:DESCRIPTION_LIMIT] if v else v


class SavePlaylistRequest(TrackListRequest, DescribedRequest):
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


# =============================================================================
# Instant Queue Models (005)
# =============================================================================


class UpdatePlaylistRequest(TrackListRequest, DescribedRequest):
    """Request to update an existing playlist."""

    playlist_id: str
    rating_keys: list[str]
    mode: Literal["replace", "append"]
    description: str = ""

    @field_validator("playlist_id")
    @classmethod
    def validate_playlist_id(cls, v: str) -> str:
        if v != "__scratch__" and not v.isdigit():
            raise ValueError("playlist_id must be '__scratch__' or a numeric rating key")
        return v


class PlayQueueRequest(TrackListRequest):
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


class ConfigResponse(BaseModel):
    """The settings the UI shows: no credential, only whether one is set."""

    version: str
    plex_url: str
    plex_connected: bool
    plex_token_set: bool
    music_library: str
    llm_provider: str
    llm_configured: bool
    llm_api_key_set: bool
    model_analysis: str  # The analysis model being used
    model_generation: str  # The generation model being used
    smart_generation: bool = False  # True if the analysis model generates too
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

    @classmethod
    def of(cls, config: MediasageConfig, plex_connected: bool) -> Self:
        """The settings the UI shows, with no secret in it.

        Only whether a credential is set is reported. Connectedness is passed
        in rather than read: this layer may not reach the Plex store.
        """
        budget = TokenBudget.of(config.llm, config.budget)

        return cls(
            version=Version.current(),
            plex_url=config.plex.url,
            plex_connected=plex_connected,
            plex_token_set=bool(config.plex.token),
            music_library=config.plex.music_library,
            llm_provider=config.llm.provider,
            llm_configured=config.llm.is_configured,
            llm_api_key_set=bool(config.llm.api_key),
            model_analysis=config.llm.model_analysis,
            model_generation=config.llm.model_generation,
            smart_generation=config.llm.smart_generation,
            max_tracks_to_ai=budget.max_tracks,
            max_albums_to_ai=budget.max_albums,
            cost_generation_input=config.llm.cost_generation_input,
            cost_generation_output=config.llm.cost_generation_output,
            cost_analysis_input=config.llm.cost_analysis_input,
            cost_analysis_output=config.llm.cost_analysis_output,
            is_priced=config.llm.is_priced,
            defaults=config.defaults,
            endpoint_url=config.llm.local_endpoint,
            context_window=config.llm.context_window,
            is_local_provider=config.llm.is_local,
            # The form disables the provider field when the environment sets it:
            # a saved value would be overridden on the next boot.
            provider_from_env=os.environ.get("MEDIASAGE_LLM__PROVIDER") is not None,
        )


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


class ValidatePlexRequest(BaseModel):
    """Request to validate Plex credentials during setup."""

    plex_url: str
    plex_token: SecretStr
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
    api_key: SecretStr = SecretStr("")
    endpoint_url: str = ""
    # The probe is a real completion, so a client must be buildable.
    model: str = ""
    context_window: int = 0

    @property
    def provider_name(self) -> str:
        """The provider as the wizard shows it, named before it is validated.

        An unknown provider is echoed back rather than mapped: it is what the
        error message has to quote.
        """
        return PROVIDER_LABELS.get(self.provider, self.provider)


class ValidateAIResponse(BaseModel):
    """Response from AI provider validation."""

    success: bool
    error: str | None = None
    provider_name: str = ""
