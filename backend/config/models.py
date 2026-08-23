"""Pure configuration data models.

Holds the shape and validation rules of MediaSage's settings. Where the values
come from — environment, YAML — is the concern of `MediasageConfig` in
`backend.config.settings`, not of anything here.

Nothing here guesses on the user's behalf. A provider, model name or context
window that was not configured stays absent rather than taking a value from a
table that goes stale; README.md documents what to set.

Sections are frozen: config is replaced wholesale via `model_copy(update=...)`
rather than mutated, so a stale reference can never observe a half-applied edit.

Every credential is a `SecretStr`, so a log line, a traceback or a stray
`model_dump` shows `**********` rather than the key. Reach the real value only
where it is spent, with `.get_secret_value()`.
"""

from typing import Annotated, Any, ClassVar, Final, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    TypeAdapter,
    field_validator,
    model_validator,
)

Provider = Literal["anthropic", "openai", "gemini", "ollama", "custom"]

# Shown in the settings form and the wizard; keys are provider names.
PROVIDER_LABELS: Final[dict[str, str]] = {
    "anthropic": "Anthropic (Claude)",
    "openai": "OpenAI (GPT)",
    "gemini": "Google (Gemini)",
    "ollama": "Ollama (Local)",
    "custom": "Custom (OpenAI-compatible)",
}

# Which configured model a call spends, and so which price applies.
Role = Literal["analysis", "generation"]

# Below: too small for a trimmed prompt. Above: a misconfiguration.
MIN_CONTEXT_WINDOW = 512
MAX_CONTEXT_WINDOW = 2_000_000


class ConfigSection(BaseModel):
    """Base for configuration sections: frozen, and strict about stray keys."""

    model_config = ConfigDict(frozen=True, extra="ignore", str_strip_whitespace=True)


class PlexConfig(ConfigSection):
    """Plex server connection settings, and how hard to lean on the server.

    Identity comes from a browser sign-in, not from these fields being typed;
    see `docs/plex_login.md`. Only `music_library` and the timing values are
    still settings a person edits.

    The timing values depend on the hardware Plex runs on: a NAS answers a bulk
    page slower than a desktop does, and rides closer to its own limits.
    """

    # A cache, not a setting: addresses move, and `server_id` re-resolves them.
    url: str = ""

    # The chosen server's own token; diverges from `account_token` when shared.
    token: SecretStr = SecretStr("")

    # Lists the servers. Kept so a sign-in survives a server being swapped.
    account_token: SecretStr = SecretStr("")

    # `clientIdentifier`, stable while the address is not.
    server_id: str = ""
    server_name: str = ""

    # Ours, sent as X-Plex-Client-Identifier; a new one orphans a Plex device.
    client_id: str = ""

    music_library: str = "Music"

    # Rows per bulk request; PLEXAPI_PLEXAPI_CONTAINER_SIZE is set to match.
    page_size: int = Field(default=1000, gt=0)

    # Seconds one Plex request may take before it is abandoned.
    connect_timeout: float = Field(default=30.0, gt=0)

    # Seconds before a disconnected client retries the server.
    reconnect_cooldown: float = Field(default=30.0, ge=0)

    # Seconds between retries of a transient failure; empty disables retrying.
    retry_backoff: list[float] = [1.0, 3.0, 8.0, 20.0]

    @field_validator("url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        """Plex paths are joined onto this directly, so a trailing slash doubles up."""
        return v.rstrip("/")

    @field_validator("music_library")
    @classmethod
    def reject_blank_library(cls, v: str) -> str:
        if not v:
            raise ValueError("music_library cannot be blank")
        return v


class LLMConfig(ConfigSection):
    """What every provider needs, whoever serves the model."""

    # Declared here because `label` reads it; subclasses narrow the literal.
    provider: Provider

    api_key: SecretStr = SecretStr("")
    model_analysis: str = ""
    model_generation: str = ""
    smart_generation: bool = False

    # Required: a per-model limits table goes stale, a guessed one overflows.
    context_window: int

    # Seconds before an outbound call is abandoned; slow hardware needs minutes.
    request_timeout: float = Field(default=600.0, gt=0)

    # Ceiling on one completion; raise it for models that answer at length.
    max_output_tokens: int = Field(default=8192, gt=0)

    # Attempts per call, retried with exponential backoff.
    max_retries: int = Field(default=3, ge=1, le=10)

    # Seconds for a metadata-only liveness probe; slow here means server down.
    probe_timeout: float = Field(default=5.0, gt=0)

    # Per million tokens; split by role, the two models rarely cost alike.
    cost_analysis_input: float = Field(default=0.0, ge=0.0)
    cost_analysis_output: float = Field(default=0.0, ge=0.0)
    cost_generation_input: float = Field(default=0.0, ge=0.0)
    cost_generation_output: float = Field(default=0.0, ge=0.0)

    # Whether inference runs locally, meaning no per-token cost.
    is_local: ClassVar[bool] = False

    @field_validator("context_window")
    @classmethod
    def validate_context_window(cls, v: int) -> int:
        if v < MIN_CONTEXT_WINDOW:
            raise ValueError(f"Context window must be at least {MIN_CONTEXT_WINDOW} tokens")
        if v > MAX_CONTEXT_WINDOW:
            raise ValueError(f"Context window cannot exceed {MAX_CONTEXT_WINDOW:,} tokens")
        return v

    @property
    def model_for_generation(self) -> str:
        """`smart_generation` spends the analysis model on generation too."""
        return self.model_analysis if self.smart_generation else self.model_generation

    @property
    def configured_models(self) -> tuple[str, ...]:
        """Every model name this section will ask a provider for, deduplicated."""
        wanted = (self.model_analysis, self.model_for_generation)
        return tuple(dict.fromkeys(name for name in wanted if name))

    def estimate_cost(self, role: Role, input_tokens: int, output_tokens: int) -> float:
        """Cost in USD for a call in `role`; always zero when inference is local.

        Prices are whatever the user declared. Unset means 0.0, which reads as
        "unpriced" rather than as a guess from a table that has gone stale.
        """
        if self.is_local:
            return 0.0
        per_input = getattr(self, f"cost_{role}_input")
        per_output = getattr(self, f"cost_{role}_output")
        return (input_tokens * per_input + output_tokens * per_output) / 1_000_000

    @property
    def is_configured(self) -> bool:
        """Whether the provider can be reached: a hosted one needs a key."""
        return bool(self.api_key.get_secret_value())

    @property
    def label(self) -> str:
        """The provider's name as a form should show it."""
        return PROVIDER_LABELS.get(self.provider, self.provider)

    @property
    def local_endpoint(self) -> str:
        """The URL a local server is reached at; empty for a hosted provider.

        The settings form and the Ollama probes need one answer whichever
        provider is configured, and a hosted one carries no URL to give.
        """
        return ""

    @property
    def is_priced(self) -> bool:
        """Whether any price was declared, so the UI can show cost or omit it."""
        if self.is_local:
            return True
        return any(
            (
                self.cost_analysis_input,
                self.cost_analysis_output,
                self.cost_generation_input,
                self.cost_generation_output,
            )
        )


class CloudLLMConfig(LLMConfig):
    """A hosted provider, reached with an API key."""

    provider: Literal["anthropic", "openai", "gemini"]


class LocalLLMConfig(LLMConfig):
    """A provider on the user's own hardware, reached by URL."""

    provider: Literal["ollama", "custom"]

    is_local: ClassVar[bool] = True

    endpoint_url: str

    @property
    def is_configured(self) -> bool:
        """A server on the user's own hardware is reached by URL, key or not."""
        return bool(self.endpoint_url)

    @property
    def local_endpoint(self) -> str:
        return self.endpoint_url

    @field_validator("endpoint_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        """Endpoint paths are appended to this, so a trailing slash doubles up."""
        return v.rstrip("/")


# Which class a saved section becomes is decided by its provider name.
LLMSection = Annotated[CloudLLMConfig | LocalLLMConfig, Field(discriminator="provider")]

LLM_SECTION_ADAPTER: TypeAdapter[CloudLLMConfig | LocalLLMConfig] = TypeAdapter(LLMSection)


class BudgetConfig(ConfigSection):
    """How much of the library is allowed into one prompt.

    The per-item figures are measured averages for one library line, February
    2026. They drive pre-flight budgeting only — the authoritative token counts
    come back on the response — but they vary with library naming, so they are
    the user's to tune.
    """

    tokens_per_track: int = Field(default=40, gt=0)
    tokens_per_album: int = Field(default=25, gt=0)

    # Room for tokenizer drift between the model and our estimate.
    context_buffer_fraction: float = Field(default=0.10, ge=0.0, lt=1.0)

    # Room for the system prompt and the model's own answer.
    reserved_prompt_tokens: int = Field(default=1000, ge=0)


class LibraryConfig(ConfigSection):
    """How the local mirror of the Plex library is synced and read.

    Every value here depends on the deployment or on taste: how big a Plex
    server is, how the user names their albums, how often they listen. None of
    them are structural, so none are baked into the code.
    """

    # Rows per transaction; also how often progress and the resume checkpoint move.
    sync_batch_size: int = Field(default=500, gt=0)

    # Hours before the cache is treated as stale and worth re-syncing.
    stale_after_hours: int = Field(default=24, gt=0)

    # Seconds a live stats read is reused; 0 disables it.
    # Plex takes 8.75s aggregating track genres over an 80k library.
    stats_cache_seconds: float = Field(default=600.0, ge=0)

    # Average plays per track at which an album counts as well-loved.
    well_loved_avg_plays: float = Field(default=3.0, gt=0)

    # Words in a title or album that mark a recording as a live performance.
    live_keywords: list[str] = ["live", "concert", "sbd", "bootleg"]

    # Whether a date in the title also marks it live; false for dated studio work.
    dated_titles_are_live: bool = True


class ResearchConfig(ConfigSection):
    """Where external research is fetched from, and how much of it is kept.

    The three endpoints are overridable because MusicBrainz and the Cover Art
    Archive both publish mirrors a self-hoster can run; the character caps are
    how much of a source fits alongside the album list in one prompt, which
    moves with the context window the user configured.
    """

    # Seconds one research call may take; research must not block a pitch.
    request_timeout: float = Field(default=10.0, gt=0)

    # Source endpoints; point these at a local mirror if one is running.
    musicbrainz_url: str = "https://musicbrainz.org/ws/2"
    cover_art_url: str = "https://coverartarchive.org"
    wikipedia_api_url: str = "https://en.wikipedia.org/w/api.php"

    # Seconds between MusicBrainz calls; their published limit is one a second.
    musicbrainz_interval: float = Field(default=1.0, ge=0)

    # Characters kept from one article, after the sections below are dropped.
    wikipedia_max_chars: int = Field(default=8000, gt=0)

    # Section titles containing any of these are tables rendered as prose.
    wikipedia_drop_sections: list[str] = [
        "track listing",
        "chart",
        "certification",
        "personnel",
        "credits",
        "reference",
        "external link",
        "see also",
        "note",
        "footnote",
        "accolade",
        "award",
        "release history",
        "singles",
        "bibliography",
        "further reading",
        "citation",
        "reissue",
        "remaster",
    ]

    # Reviews read per album, and the characters kept from each.
    max_reviews: int = Field(default=2, ge=0)
    review_max_chars: int = Field(default=2000, gt=0)

    # Earliest character a sentence break is accepted at when trimming a review.
    review_min_chars: int = Field(default=1500, ge=0)

    # Never fetched; AllMusic's terms prohibit automated access.
    blocked_review_hosts: list[str] = ["allmusic.com"]

    # Redirect hops followed before giving up; each hop is re-checked as safe.
    max_redirects: int = Field(default=5, ge=0)

    @model_validator(mode="after")
    def check_review_bounds(self) -> Self:
        """A break floor above the cap would trim every review to the cap."""
        if self.review_min_chars > self.review_max_chars:
            raise ValueError("review_min_chars cannot exceed review_max_chars")
        return self


class MatchingConfig(ConfigSection):
    """How close a name has to be before it counts as the same record.

    Scores are rapidfuzz ratios over accent-folded, punctuation-stripped text,
    0-100. The right floor depends entirely on how a library is tagged: clean
    tags tolerate a high one, a library full of "(Remastered)" suffixes needs a
    lower one. Too low plays the wrong record; too high drops good matches.
    """

    # Floor for matching a track the model named against the library.
    track_threshold: int = Field(default=60, ge=0, le=100)

    # Picking a library album: a wrong match here plays the wrong record.
    album_artist_min: int = Field(default=70, ge=0, le=100)
    album_combined_min: int = Field(default=70, ge=0, le=100)

    # Attaching a pitch; the prompt named the album, so the artist is sure.
    pitch_artist_min: int = Field(default=80, ge=0, le=100)
    pitch_album_min: int = Field(default=60, ge=0, le=100)


class RecommendConfig(ConfigSection):
    """The shape of one recommendation round, and how long a flow is held.

    Sessions live in memory, so the caps are a memory budget rather than a
    policy; the pick counts are how much a user wants to read at once.
    """

    # Seconds an untouched session survives, and how many are held at once.
    session_expiry: int = Field(default=1800, gt=0)
    max_sessions: int = Field(default=100, gt=0)

    # Albums remembered per session, so "Show me another" stops repeating.
    recent_limit: int = Field(default=30, ge=0)

    # Dimensions one round asks the user about before picking.
    question_count: int = Field(default=2, ge=0)

    # Albums one round shows: one primary and the rest secondary.
    pick_count: int = Field(default=3, gt=0)

    # Discovery asks for more than it shows; owned albums are filtered after.
    discovery_request: int = Field(default=7, gt=0)

    # Below this many candidates the model is told the pool is thin.
    small_pool: int = Field(default=10, ge=0)

    # Owned albums listed in the discovery prompt; the rest are filtered after.
    max_exclusion_albums: int = Field(default=2500, gt=0)

    # Genres per album line; more is noise the model ignores.
    genres_per_line: int = Field(default=3, ge=0)


class ArtConfig(ConfigSection):
    """How album art is proxied, and how long a browser may keep it.

    Plex mints a new thumb path when artwork changes, so its art is content-
    addressed and can be cached hard; external art is not, and gets less.
    """

    # Seconds an art fetch may take; art must never block a page.
    timeout: float = Field(default=10.0, gt=0)

    # Seconds a browser may reuse a cached image.
    cache_max_age: int = Field(default=604800, ge=0)
    external_cache_max_age: int = Field(default=86400, ge=0)

    # Hosts external art may be fetched from, subdomains included.
    external_domains: list[str] = ["coverartarchive.org", "archive.org"]

    # Redirect hops followed; the Cover Art Archive's chain is two.
    max_redirects: int = Field(default=5, ge=0)


class DefaultsConfig(ConfigSection):
    """Default values presented in the UI."""

    track_count: int = Field(default=25, ge=1, le=1000)


# Fields whose value decides whether a dependency answers at all. Everything
# else in an update -- prices, and the music library name Plex resolves later --
# is saved on its own word.
CONNECTING: Final[frozenset[str]] = frozenset(
    {
        "llm_provider",
        "llm_api_key",
        "endpoint_url",
        "model_analysis",
        "model_generation",
        "context_window",
    }
)


class ConfigUpdate(ConfigSection):
    """A partial configuration change submitted from the UI.

    Owns the mapping from API field names to the section and key they write, so
    neither the route nor the store has to restate it.

    No Plex identity here: the address and both tokens come from a browser
    sign-in, written by `/api/plex/*`. `music_library` is all a form still says
    about Plex.
    """

    music_library: str | None = None
    llm_provider: Provider | None = None
    llm_api_key: SecretStr | None = None
    model_analysis: str | None = None
    model_generation: str | None = None
    smart_generation: bool | None = None

    endpoint_url: str | None = None
    context_window: int | None = None
    cost_analysis_input: float | None = None
    cost_analysis_output: float | None = None
    cost_generation_input: float | None = None
    cost_generation_output: float | None = None

    # Field name -> the section and key it writes.
    FIELD_MAP: ClassVar[dict[str, tuple[str, str]]] = {
        "music_library": ("plex", "music_library"),
        "llm_provider": ("llm", "provider"),
        "llm_api_key": ("llm", "api_key"),
        "model_analysis": ("llm", "model_analysis"),
        "model_generation": ("llm", "model_generation"),
        "smart_generation": ("llm", "smart_generation"),
        "endpoint_url": ("llm", "endpoint_url"),
        "context_window": ("llm", "context_window"),
        "cost_analysis_input": ("llm", "cost_analysis_input"),
        "cost_analysis_output": ("llm", "cost_analysis_output"),
        "cost_generation_input": ("llm", "cost_generation_input"),
        "cost_generation_output": ("llm", "cost_generation_output"),
    }

    @property
    def provider_changes(self) -> dict[str, Any]:
        """Clear what belonged to the previous provider.

        Model names, endpoints and prices do not survive a provider switch: they
        name things the new provider does not serve. Anything the caller supplied
        explicitly is left for `changes` to apply over the top.

        `context_window` is deliberately kept: it is required, so blanking it
        would leave the section unvalidatable until the user supplies a new one.
        """
        derived: dict[str, Any] = {"provider": self.llm_provider}

        for field, supplied, blank in (
            ("model_analysis", self.model_analysis, ""),
            ("model_generation", self.model_generation, ""),
            ("endpoint_url", self.endpoint_url, ""),
            ("cost_analysis_input", self.cost_analysis_input, 0.0),
            ("cost_analysis_output", self.cost_analysis_output, 0.0),
            ("cost_generation_input", self.cost_generation_input, 0.0),
            ("cost_generation_output", self.cost_generation_output, 0.0),
        ):
            if supplied is None:
                derived[field] = blank

        return derived

    @staticmethod
    def plain(value: Any) -> Any:
        """A secret as the string that has to reach YAML and the provider.

        Left wrapped, a credential would be written to `config.user.yaml` as
        the mask and the deployment would come back up unconfigured.
        """
        return value.get_secret_value() if isinstance(value, SecretStr) else value

    def changes(self, section: str) -> dict[str, Any]:
        """Supplied values for one section, keyed as that section names them.

        Presence is `is not None`, not truthiness: a price of `0.0` and a
        `context_window` of `0` are values the caller asked for, and dropping
        them made a cost impossible to clear and an all-zero body a 400.

        Args:
            section: Either `plex` or `llm`

        Returns:
            The section's changed keys; empty when nothing was supplied for it
        """
        supplied = self.model_dump()
        return {
            key: self.plain(supplied[field])
            for field, (owner, key) in self.FIELD_MAP.items()
            if owner == section and supplied[field] is not None
        }

    def touches(self, section: str) -> bool:
        """Whether that section's client must be rebuilt after applying this."""
        return bool(self.changes(section))

    def reconnects(self, section: str) -> bool:
        """Whether this change could stop that section's dependency answering.

        Narrower than `touches`: a price is a number the UI reports back, so
        editing one must not spend a completion, nor fail because the provider
        happens to be down.
        """
        supplied = self.model_dump()
        return any(
            field in CONNECTING
            for field, (owner, _) in self.FIELD_MAP.items()
            if owner == section and supplied[field] is not None
        )

    @property
    def is_empty(self) -> bool:
        """Whether the request asks for no change at all."""
        return not (self.touches("plex") or self.touches("llm"))
