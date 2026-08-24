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
    create_model,
    field_validator,
    model_validator,
)
from pydantic.fields import FieldInfo

Provider = Literal["anthropic", "openai", "gemini", "ollama", "custom"]

# Shown in the settings form and the wizard; keys are provider names.
PROVIDER_LABELS: Final[dict[str, str]] = {
    "anthropic": "Anthropic (Claude)",
    "openai": "OpenAI (GPT)",
    "gemini": "Google (Gemini)",
    "ollama": "Ollama (Local)",
    "custom": "Custom (OpenAI-compatible)",
}

# Restated on all three declarations: a subclass narrowing the literal
# redeclares the field, and a redeclared field inherits no description.
PROVIDER_HINT: Final = "Who serves the model. Changing it clears the model names and the key."

# Which configured model a call spends, and so which price applies.
Role = Literal["analysis", "generation"]

# Below: too small for a trimmed prompt. Above: a misconfiguration.
MIN_CONTEXT_WINDOW = 512
MAX_CONTEXT_WINDOW = 2_000_000


class ConfigPatch(BaseModel):
    """Base for the partial form of a section: every field absent by default.

    Presence is what a change means here, not a non-null value: `temperature`
    is legitimately `None`, and clearing it back to the server's own default
    has to be expressible. `model_dump(exclude_unset=True)` is the only correct
    way to read one.

    `extra="forbid"`, unlike the sections themselves: a settings API that
    silently drops a misspelled field is one a form cannot be debugged against.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class ConfigSection(BaseModel):
    """Base for configuration sections: frozen, and strict about stray keys."""

    model_config = ConfigDict(frozen=True, extra="ignore", str_strip_whitespace=True)

    # Fields no form may write; see `PlexConfig` for the only case.
    UNEDITABLE: ClassVar[frozenset[str]] = frozenset()

    @classmethod
    def patch(cls, name: str, **overrides: Any) -> type[ConfigPatch]:
        """This section with every editable field optional and unset.

        Derived rather than declared, so a field's type and its bounds are
        stated once -- on the section -- and a new setting needs no second
        entry anywhere to become editable.

        Args:
            name: The generated model's name, which is what codegen emits
            overrides: Replacement annotations for fields a subclass narrows
                further than a form should; `LLMPatch` needs one for `provider`

        Returns:
            A `ConfigPatch` subclass over this section's editable fields
        """
        fields: dict[str, Any] = {
            field: cls.optional(info, overrides.get(field))
            for field, info in cls.model_fields.items()
            if field not in cls.UNEDITABLE
        }
        return create_model(name, __base__=ConfigPatch, **fields)

    @staticmethod
    def optional(info: FieldInfo, override: Any = None) -> tuple[Any, Any]:
        """One field, absent by default, with its constraints intact.

        The constraints stay inside the `Annotated` rather than outside the
        union: `gt=0` applied to `T | None` rejects the unset case.
        """
        annotation: Any = override if override is not None else info.annotation
        if info.metadata:
            annotation = Annotated[(annotation, *info.metadata)]
        return (annotation | None, Field(default=None, description=info.description))


class PlexConfig(ConfigSection):
    """Plex server connection settings, and how hard to lean on the server.

    Identity comes from a browser sign-in, not from these fields being typed;
    see `docs/plex_login.md`. Only `music_library` and the timing values are
    still settings a person edits.

    The timing values depend on the hardware Plex runs on: a NAS answers a bulk
    page slower than a desktop does, and rides closer to its own limits.
    """

    # Written by `/api/plex/*` from a sign-in, so shown but never edited.
    # Also what `backend.config.settings` drops from the environment sources.
    UNEDITABLE: ClassVar[frozenset[str]] = frozenset(
        {"url", "token", "account_token", "server_id", "client_id", "server_name"}
    )

    url: str = Field(
        default="",
        description="A cache, not a setting: addresses move, and the server id re-resolves them.",
    )
    token: SecretStr = Field(
        default=SecretStr(""),
        description="The chosen server's own token; diverges from the account token when shared.",
    )
    account_token: SecretStr = Field(
        default=SecretStr(""),
        description="Lists the servers. Kept so a sign-in survives a server being swapped.",
    )
    server_id: str = Field(
        default="",
        description="Plex's `clientIdentifier` for the server, stable while the address is not.",
    )
    server_name: str = Field(
        default="", description="The signed-in server's name, as Plex reports it."
    )
    client_id: str = Field(
        default="",
        description="Ours, sent as X-Plex-Client-Identifier; a new one orphans a Plex device.",
    )
    music_library: str = Field(
        default="Music", description="Which Plex library section holds the music."
    )
    page_size: int = Field(
        default=1000,
        gt=0,
        description="Rows per bulk request; PLEXAPI_PLEXAPI_CONTAINER_SIZE is set to match.",
    )
    connect_timeout: float = Field(
        default=30.0,
        gt=0,
        description="Seconds one Plex request may take before it is abandoned.",
    )
    reconnect_cooldown: float = Field(
        default=30.0,
        ge=0,
        description="Seconds before a disconnected client retries the server.",
    )
    retry_backoff: list[float] = Field(
        default=[1.0, 3.0, 8.0, 20.0],
        description="Seconds between retries of a transient failure; empty disables retrying.",
    )
    genre_workers: int = Field(
        default=8,
        gt=0,
        le=64,
        description=(
            "Concurrent genre queries during a sync; 1 keeps that stage serial. "
            "8 because it is one request per genre, and a big library has hundreds."
        ),
    )

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
    provider: Provider = Field(description=PROVIDER_HINT)

    api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Credential for a hosted provider. A local server usually needs none.",
    )
    model_analysis: str = Field(
        default="",
        description="Reads the prompt and picks the tracks. The stronger model belongs here.",
    )
    model_generation: str = Field(
        default="",
        description="Writes the playlist from the filtered list. A cheaper model does.",
    )
    smart_generation: bool = Field(
        default=False,
        description="Spend the analysis model on generation too: better results, higher cost.",
    )
    context_window: int = Field(
        description="Required: a per-model limits table goes stale, and a guessed one overflows.",
    )
    request_timeout: float = Field(
        default=600.0,
        gt=0,
        description="Seconds before an outbound call is abandoned; slow hardware needs minutes.",
    )
    stream_idle_timeout: float = Field(
        default=600.0,
        gt=0,
        description=(
            "Seconds of silence on a generate stream before the browser gives up. "
            "Measured per frame: a model may think for minutes between them."
        ),
    )
    max_output_tokens: int = Field(
        default=8192,
        gt=0,
        description="Ceiling on one completion; raise it for models that answer at length.",
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Attempts per call, retried with exponential backoff.",
    )

    # Sampling: unset is not sent, leaving the server's own default.
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Randomness. Unset sends nothing, leaving the server's own default.",
    )
    top_p: float | None = Field(
        default=None,
        gt=0.0,
        le=1.0,
        description="Nucleus sampling mass. Unset sends nothing; the model card names a value.",
    )
    top_k: int | None = Field(
        default=None,
        ge=0,
        description="Candidate tokens considered per step. Unset sends nothing.",
    )
    min_p: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Floor on a token's probability, relative to the best one. Unset sends nothing.",
    )
    presence_penalty: float | None = Field(
        default=None,
        ge=-2.0,
        le=2.0,
        description="Pushes the model off tokens it has already used. Unset sends nothing.",
    )
    repetition_penalty: float | None = Field(
        default=None,
        gt=0.0,
        le=2.0,
        description="Divides the score of repeated tokens. Unset sends nothing.",
    )
    probe_timeout: float = Field(
        default=5.0,
        gt=0,
        description="Seconds for a metadata-only liveness probe; slow here means server down.",
    )
    cost_analysis_input: float = Field(
        default=0.0,
        ge=0.0,
        description="USD per million input tokens on the analysis model. 0 reports no cost.",
    )
    cost_analysis_output: float = Field(
        default=0.0,
        ge=0.0,
        description="USD per million output tokens on the analysis model. 0 reports no cost.",
    )
    cost_generation_input: float = Field(
        default=0.0,
        ge=0.0,
        description="USD per million input tokens on the generation model. 0 reports no cost.",
    )
    cost_generation_output: float = Field(
        default=0.0,
        ge=0.0,
        description="USD per million output tokens on the generation model. 0 reports no cost.",
    )

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

    provider: Literal["anthropic", "openai", "gemini"] = Field(description=PROVIDER_HINT)


class LocalLLMConfig(LLMConfig):
    """A provider on the user's own hardware, reached by URL."""

    provider: Literal["ollama", "custom"] = Field(description=PROVIDER_HINT)

    is_local: ClassVar[bool] = True

    endpoint_url: str = Field(
        description="Where the local server listens, including any /v1 suffix it expects.",
    )

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

    tokens_per_track: int = Field(
        default=40,
        gt=0,
        description="Measured average for one track line. Longer titles need more.",
    )
    tokens_per_album: int = Field(
        default=25,
        gt=0,
        description="Measured average for one album line. Longer titles need more.",
    )
    context_buffer_fraction: float = Field(
        default=0.10,
        ge=0.0,
        lt=1.0,
        description="Room for tokenizer drift between the model and our estimate.",
    )
    reserved_prompt_tokens: int = Field(
        default=1000,
        ge=0,
        description="Room for the system prompt and the model's own answer.",
    )


class LibraryConfig(ConfigSection):
    """How the local mirror of the Plex library is synced and read.

    Every value here depends on the deployment or on taste: how big a Plex
    server is, how the user names their albums, how often they listen. None of
    them are structural, so none are baked into the code.
    """

    sync_batch_size: int = Field(
        default=500,
        gt=0,
        description="Rows per transaction, and how often progress and the resume point move.",
    )
    stale_after_hours: int = Field(
        default=24,
        gt=0,
        description="Hours before the cache is treated as stale and worth re-syncing.",
    )
    stats_cache_seconds: float = Field(
        default=600.0,
        ge=0,
        description=(
            "Seconds a live stats read is reused; 0 disables it. "
            "Plex takes 8.75s aggregating track genres over an 80k library."
        ),
    )
    well_loved_avg_plays: float = Field(
        default=3.0,
        gt=0,
        description="Average plays per track at which an album counts as well-loved.",
    )
    live_keywords: list[str] = Field(
        default=["live", "concert", "sbd", "bootleg"],
        description="Words in a title or album that mark a recording as a live performance.",
    )
    dated_titles_are_live: bool = Field(
        default=True,
        description="Whether a date in the title also marks it live. Off for dated studio work.",
    )


class ResearchConfig(ConfigSection):
    """Where external research is fetched from, and how much of it is kept.

    The three endpoints are overridable because MusicBrainz and the Cover Art
    Archive both publish mirrors a self-hoster can run; the character caps are
    how much of a source fits alongside the album list in one prompt, which
    moves with the context window the user configured.
    """

    request_timeout: float = Field(
        default=10.0,
        gt=0,
        description="Seconds one research call may take; research must not block a pitch.",
    )
    musicbrainz_url: str = Field(
        default="https://musicbrainz.org/ws/2",
        description="Point this at a local MusicBrainz mirror if one is running.",
    )
    cover_art_url: str = Field(
        default="https://coverartarchive.org",
        description="Point this at a local Cover Art Archive mirror if one is running.",
    )
    wikipedia_api_url: str = Field(
        default="https://en.wikipedia.org/w/api.php",
        description="A different language edition changes which articles are read.",
    )
    musicbrainz_interval: float = Field(
        default=1.0,
        ge=0,
        description=(
            "Seconds between MusicBrainz calls; their published limit is one a second. "
            "Drop it to 0 against your own mirror."
        ),
    )
    wikipedia_max_chars: int = Field(
        default=8000,
        gt=0,
        description="Characters kept from one article, after the dropped sections go.",
    )
    wikipedia_drop_sections: list[str] = Field(
        default=[
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
        ],
        description="A section whose title contains any of these is a table rendered as prose.",
    )
    max_reviews: int = Field(
        default=2, ge=0, description="Reviews read per album. 0 skips reviews entirely."
    )
    review_max_chars: int = Field(
        default=2000, gt=0, description="Characters kept from one review."
    )
    review_min_chars: int = Field(
        default=1500,
        ge=0,
        description="Earliest character a sentence break is accepted at when trimming a review.",
    )
    blocked_review_hosts: list[str] = Field(
        default=["allmusic.com"],
        description="Never fetched; AllMusic's terms prohibit automated access.",
    )
    max_redirects: int = Field(
        default=5,
        ge=0,
        description="Redirect hops followed before giving up; each hop is re-checked as safe.",
    )

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

    track_threshold: int = Field(
        default=60,
        ge=0,
        le=100,
        description="Floor for matching a track the model named against the library.",
    )
    album_artist_min: int = Field(
        default=70,
        ge=0,
        le=100,
        description="Artist floor when picking a library album. Too low plays the wrong record.",
    )
    album_combined_min: int = Field(
        default=70,
        ge=0,
        le=100,
        description="Artist and title scored together when picking a library album.",
    )
    pitch_artist_min: int = Field(
        default=80,
        ge=0,
        le=100,
        description="Artist floor when attaching a pitch. High: the prompt named the album.",
    )
    pitch_album_min: int = Field(
        default=60, ge=0, le=100, description="Album-title floor when attaching a pitch."
    )


class RecommendConfig(ConfigSection):
    """The shape of one recommendation round, and how long a flow is held.

    Sessions live in memory, so the caps are a memory budget rather than a
    policy; the pick counts are how much a user wants to read at once.
    """

    session_expiry: int = Field(
        default=1800, gt=0, description="Seconds an untouched recommendation session survives."
    )
    max_sessions: int = Field(
        default=100, gt=0, description="Sessions held in memory at once, across all users."
    )
    recent_limit: int = Field(
        default=30,
        ge=0,
        description='Albums remembered per session, so "Show me another" stops repeating.',
    )
    question_count: int = Field(
        default=2, ge=0, description="Dimensions one round asks the user about before picking."
    )
    pick_count: int = Field(
        default=3, gt=0, description="Albums one round shows: one primary and the rest secondary."
    )
    discovery_request: int = Field(
        default=7,
        gt=0,
        description="Discovery asks for more than it shows; owned albums are filtered after.",
    )
    small_pool: int = Field(
        default=10,
        ge=0,
        description="Below this many candidates the model is told the pool is thin.",
    )
    max_exclusion_albums: int = Field(
        default=2500,
        gt=0,
        description="Owned albums listed in the discovery prompt; the rest are filtered after.",
    )
    genres_per_line: int = Field(
        default=3, ge=0, description="Genres per album line; more is noise the model ignores."
    )


class ArtConfig(ConfigSection):
    """How album art is proxied, and how long a browser may keep it.

    Plex mints a new thumb path when artwork changes, so its art is content-
    addressed and can be cached hard; external art is not, and gets less.
    """

    timeout: float = Field(
        default=10.0,
        gt=0,
        description="Seconds an art fetch may take; art must never block a page.",
    )
    cache_max_age: int = Field(
        default=604800,
        ge=0,
        description="Seconds a browser may reuse Plex art. Long: its thumb paths are content-addressed.",
    )
    external_cache_max_age: int = Field(
        default=86400,
        ge=0,
        description="Seconds a browser may reuse external art, which carries no content address.",
    )
    external_domains: list[str] = Field(
        default=["coverartarchive.org", "archive.org"],
        description="Hosts external art may be fetched from, subdomains included.",
    )
    max_redirects: int = Field(
        default=5,
        ge=0,
        description="Redirect hops followed; the Cover Art Archive's chain is two.",
    )


class DefaultsConfig(ConfigSection):
    """Default values presented in the UI."""

    track_count: int = Field(
        default=25,
        ge=1,
        le=1000,
        description="Playlist length the create forms open on.",
    )


class LangfuseConfig(ConfigSection):
    """Where LLM traces are sent, and the keys that sign them.

    Tracing stays off until all three are set. No default endpoint: pointing an
    unconfigured deployment at a cloud it never chose would send prompts
    somewhere the operator did not ask for.

    Reachable under Langfuse's own variable names as well as
    `MEDIASAGE_LANGFUSE__*`; see `LangfuseEnv` in `backend.config.settings`.
    """

    base_url: str = Field(
        default="",
        description="A Langfuse cloud region, or a self-hosted URL. Empty means no tracing.",
    )

    # Not a SecretStr: Langfuse publishes this key to browsers by design.
    public_key: str = Field(
        default="", description="The project's public key. Langfuse publishes it to browsers."
    )
    secret_key: SecretStr = Field(
        default=SecretStr(""),
        description="The project's secret key. Paired with the public key, it authenticates ingestion.",
    )
    environment: str = Field(
        default="",
        description="Which Langfuse environment traces land in. Empty leaves the SDK's own.",
    )

    @property
    def is_configured(self) -> bool:
        """Whether a trace has somewhere to go and something to sign it."""
        return bool(self.base_url and self.public_key and self.secret_key.get_secret_value())


# Keys whose value decides whether a section's dependency answers at all,
# per section. Everything else -- prices, thresholds, the music library name
# Plex resolves later -- is saved on the caller's own word.
CONNECTING: Final[dict[str, frozenset[str]]] = {
    "llm": frozenset(
        {
            "provider",
            "api_key",
            "endpoint_url",
            "model_analysis",
            "model_generation",
            "context_window",
        }
    )
}

PlexPatch = PlexConfig.patch("PlexPatch")
# From the local subclass, which is the superset: only it declares
# `endpoint_url`. Its `provider` literal is widened back to every provider.
LLMPatch = LocalLLMConfig.patch("LLMPatch", provider=Provider)
BudgetPatch = BudgetConfig.patch("BudgetPatch")
LibraryPatch = LibraryConfig.patch("LibraryPatch")
MatchingPatch = MatchingConfig.patch("MatchingPatch")
RecommendPatch = RecommendConfig.patch("RecommendPatch")
ResearchPatch = ResearchConfig.patch("ResearchPatch")
ArtPatch = ArtConfig.patch("ArtPatch")
DefaultsPatch = DefaultsConfig.patch("DefaultsPatch")
LangfusePatch = LangfuseConfig.patch("LangfusePatch")


class ConfigUpdate(BaseModel):
    """A partial configuration change submitted from the UI.

    Shaped like `MediasageConfig`: one optional patch per section, each derived
    from the section it writes. There is no field-name table, so a setting
    added to a section is submittable the moment it exists.

    No Plex identity here -- `PlexConfig.UNEDITABLE` keeps it out of `PlexPatch`
    -- because the address and both tokens come from a browser sign-in.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    plex: PlexPatch | None = None
    llm: LLMPatch | None = None
    budget: BudgetPatch | None = None
    library: LibraryPatch | None = None
    matching: MatchingPatch | None = None
    recommend: RecommendPatch | None = None
    research: ResearchPatch | None = None
    art: ArtPatch | None = None
    defaults: DefaultsPatch | None = None
    langfuse: LangfusePatch | None = None

    @classmethod
    def sections(cls) -> tuple[str, ...]:
        """Every section an update can carry, in declaration order."""
        return tuple(cls.model_fields)

    @property
    def provider_changes(self) -> dict[str, Any]:
        """Clear what belonged to the previous provider.

        Model names, endpoints and prices do not survive a provider switch: they
        name things the new provider does not serve. Anything the caller supplied
        explicitly is left for `changes` to apply over the top.

        `context_window` is deliberately kept: it is required, so blanking it
        would leave the section unvalidatable until the user supplies a new one.
        """
        supplied = self.changes("llm")
        derived: dict[str, Any] = {"provider": supplied["provider"]}

        for field, blank in (
            ("model_analysis", ""),
            ("model_generation", ""),
            ("endpoint_url", ""),
            ("cost_analysis_input", 0.0),
            ("cost_analysis_output", 0.0),
            ("cost_generation_input", 0.0),
            ("cost_generation_output", 0.0),
        ):
            if field not in supplied:
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

        Presence, not a non-null value: `temperature` is legitimately `None`,
        and clearing it back to the provider's own default has to be something
        a form can ask for.

        Args:
            section: One of `sections()`

        Returns:
            The section's changed keys; empty when nothing was supplied for it
        """
        patch = getattr(self, section, None)
        if patch is None:
            return {}
        return {
            key: self.plain(value) for key, value in patch.model_dump(exclude_unset=True).items()
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
        return bool(CONNECTING.get(section, frozenset()) & self.changes(section).keys())

    @property
    def is_empty(self) -> bool:
        """Whether the request asks for no change at all."""
        return not any(self.touches(section) for section in self.sections())
