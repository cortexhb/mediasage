"""Pydantic models for MediaSage API contracts and internal data structures."""

import os
from typing import Annotated, Any, Final, Literal, Self

from pydantic import BaseModel, Field, SecretStr, TypeAdapter, field_validator, model_validator

from backend.config.models import PROVIDER_LABELS
from backend.config.settings import LANGFUSE_ENV, MediasageConfig
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
    flow_id: str = ""


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
    flow_id: str = ""


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
    """How much of the library one filter selection reaches.

    Counts only. What a run will cost is not predicted: the tokens it spends
    are reported by the provider once the calls have been made.
    """

    # -1 where the count is unknown: an unsynced cache reports that.
    matching_tracks: int
    tracks_to_send: int

    @classmethod
    def of(cls, request: FilterPreviewRequest, matching_tracks: int) -> Self:
        """What `matching_tracks` of the library means for this selection."""
        return cls(
            matching_tracks=matching_tracks,
            tracks_to_send=cls.capped(matching_tracks, request.max_tracks_to_ai),
        )

    @staticmethod
    def capped(available: int, limit: int) -> int:
        """How many rows are actually sent; a limit of zero means all of them."""
        if available <= 0:
            return 0
        return min(available, limit) if limit > 0 else available


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
    # The client's id for this flow; groups its traces into one session.
    flow_id: str = ""

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

    @property
    def answered(self) -> dict[str, Any]:
        """The playlist as a trace shows it: what was picked, not every field."""
        return {
            "playlist_title": self.playlist_title,
            "narrative": self.narrative,
            "tracks": [f"{track.artist} - {track.title}" for track in self.tracks],
            "token_count": self.token_count,
            "estimated_cost": self.estimated_cost,
        }


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
    """Every setting the UI shows, plus the facts it cannot compute itself.

    `sections` is the configuration as loaded, so a field added to a section
    reaches the form without a second declaration here. Credentials inside it
    serialise as `**********`; `llm_api_key_set` is how a form knows one is
    there at all.

    Everything outside `sections` is derived: a version, a live connection, a
    budget computed from the context window, or a fact about the environment.
    """

    version: str
    sections: MediasageConfig

    plex_connected: bool
    plex_linked: bool  # True once a browser sign-in has stored a token
    llm_configured: bool
    llm_api_key_set: bool
    max_tracks_to_ai: int  # Recommended max tracks for this model
    max_albums_to_ai: int  # Recommended max albums for this model
    is_priced: bool = False
    is_local_provider: bool = False

    # `section.field` paths the environment sets; a save cannot beat them.
    from_env: list[str] = []

    @classmethod
    def of(cls, config: MediasageConfig, plex_connected: bool) -> Self:
        """The settings the UI shows, with no secret in it.

        Only whether a credential is set is reported. Connectedness is passed
        in rather than read: this layer may not reach the Plex store.
        """
        budget = TokenBudget.of(config.llm, config.budget)

        return cls(
            version=Version.current(),
            sections=config,
            plex_connected=plex_connected,
            plex_linked=bool(config.plex.account_token),
            llm_configured=config.llm.is_configured,
            llm_api_key_set=bool(config.llm.api_key),
            max_tracks_to_ai=budget.max_tracks,
            max_albums_to_ai=budget.max_albums,
            is_priced=config.llm.is_priced,
            is_local_provider=config.llm.is_local,
            from_env=cls.overridden(),
        )

    @staticmethod
    def overridden() -> list[str]:
        """Which settings the environment pins, as `section.field` paths.

        The form disables these: a saved value would be overridden on the next
        boot, so offering the field would be a lie. Read from `os.environ`
        rather than listed, so a new setting needs no entry here.
        """
        prefix = "MEDIASAGE_"
        pinned = [
            name.removeprefix(prefix).replace("__", ".", 1).lower()
            for name in os.environ
            if name.startswith(prefix) and "__" in name
        ]
        pinned += [
            f"langfuse.{field}" for name, field in LANGFUSE_ENV.items() if os.environ.get(name)
        ]
        return sorted(set(pinned))


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
    # Set by the playlist flow; groups these traces with its own.
    flow_id: str = ""


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
    music_libraries: list[str] = []
    llm_configured: bool
    llm_provider: str = ""
    llm_from_env: bool = False
    library_synced: bool
    track_count: int = 0
    is_syncing: bool = False
    sync_progress: SyncProgress | None = None


class PlexServerChoice(BaseModel):
    """One server the signed-in account can reach.

    Here rather than in `backend/plex/link.py` because `backend.plex` already
    reads this module, the way `PlexLibrary` reads `Track`.
    """

    # `clientIdentifier`, stable while the address is not.
    id: str
    name: str
    owned: bool


class PlexLinkResponse(BaseModel):
    """A pin waiting to be approved, and where to approve it."""

    pin_id: int
    code: str
    url: str
    expires_in: int


class PlexLinkStatusResponse(BaseModel):
    """Whether the pin has been approved yet, and what it unlocked."""

    # Pending until the user approves it in their browser; then linked.
    state: Literal["pending", "linked"]
    servers: list[PlexServerChoice] = []


class PlexServerRequest(BaseModel):
    """Which of the listed servers to talk to."""

    server_id: str


class PlexLinkedResponse(BaseModel):
    """What a sign-in left in force, as the Plex card shows it."""

    linked: bool
    connected: bool
    server_name: str = ""
    server_id: str = ""
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
