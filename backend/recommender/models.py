"""Domain models for the album recommendation pipeline.

What the pipeline passes between its stages: albums named by artist and title,
the answers a user gave, the pitch written for an album, and the facts that
pitch was checked against. `backend.models` keeps the request and response
models that validate HTTP traffic.
"""

from __future__ import annotations

import re
from typing import Any, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field

from backend.library import AlbumCandidate

# Joins artist and album into one lookup key. Chosen because no title contains
# it; a single separator would collide with names like "Earth, Wind & Fire".
KEY_SEPARATOR = "|||"

# Edition markers a library carries in a title and MusicBrainz does not.
# End only: "Deluxe" inside a real title is part of the title.
EDITION_SUFFIX: Final = re.compile(
    r"\s*\("
    r"(?:Explicit|Clean|Deluxe|Special|Expanded|Anniversary|Limited|"
    r"Bonus Track|Collector(?:'s)?|International|Standard|Super Deluxe|"
    r"Premium|Platinum|Ultimate|Complete|Original|Extended)"
    r"[^)]*\)\s*$",
    re.IGNORECASE,
)

# Which pick a recommendation is: one primary, the rest secondary.
Rank = Literal["primary", "secondary"]

# Which mode a session is generating in.
Mode = Literal["library", "discovery"]

# How adventurous the user wants the picks to be.
FamiliarityPreference = Literal["any", "comfort", "rediscover", "hidden_gems"]


class AlbumRef(BaseModel):
    """One album, named the way a model names it.

    Everything crossing a pipeline stage is keyed on this rather than on a
    joined string, so the artist and album never have to be parsed back out.
    """

    model_config = ConfigDict(frozen=True)

    artist: str
    album: str

    @property
    def key(self) -> str:
        """Case-folded lookup key; a model's casing rarely matches the library's."""
        return f"{self.artist.lower()}{KEY_SEPARATOR}{self.album.lower()}"

    def __str__(self) -> str:
        return f"{self.artist} — {self.album}"

    def without_edition(self) -> Self | None:
        """The same album with its edition suffix dropped, or None if it had none.

        A library files "Nevermind (Deluxe Edition)"; MusicBrainz files
        "Nevermind". Only the end is stripped, so a title that really is called
        "Deluxe Trouble" keeps its name.
        """
        stripped = EDITION_SUFFIX.sub("", self.album).strip()
        if not stripped or stripped == self.album:
            return None
        return self.model_copy(update={"album": stripped})

    @classmethod
    def parse(cls, key: str) -> Self | None:
        """Read a key back into its two halves; None when it is not one."""
        artist, separator, album = key.partition(KEY_SEPARATOR)
        return cls(artist=artist, album=album) if separator else None


class TasteDimension(BaseModel):
    """One axis a clarifying question can be asked along."""

    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    description: str

    def line(self) -> str:
        """How the dimension is offered to the model."""
        return f"- {self.id}: {self.label} — {self.description}"


class AnswerSet(BaseModel):
    """What the user answered, and the free text they added.

    A skipped question is a None answer, which the prompts must still account
    for: the model is told a question was skipped rather than left to guess.
    """

    answers: list[str | None] = []
    texts: list[str] = []

    def _text_for(self, index: int) -> str:
        return self.texts[index] if index < len(self.texts) else ""

    def for_selection(self) -> str:
        """One labelled line per question, skips included."""
        lines = []
        for index, answer in enumerate(self.answers):
            if not answer:
                lines.append(f"Q{index + 1}: skipped")
                continue
            extra = self._text_for(index)
            lines.append(f"Q{index + 1} answer: {answer}" + (f" (also: {extra})" if extra else ""))
        return "\n".join(lines)

    def for_pitch(self) -> str:
        """A compact one-liner; skips are simply absent."""
        parts = []
        for index, answer in enumerate(self.answers):
            if not answer:
                continue
            extra = self._text_for(index)
            parts.append(f"{answer} ({extra})" if extra else answer)
        return "; ".join(parts) if parts else "no specific preferences"


class ClarifyingQuestion(BaseModel):
    """A question put to the user before albums are picked."""

    question_text: str
    options: list[str]
    dimension: str


class SommelierPitch(BaseModel):
    """The editorial writeup for a recommendation.

    A primary pick fills the four long fields; a secondary one fills only
    `short_pitch`. `full_text` is what the fact-checker reads.
    """

    hook: str = ""
    context: str = ""
    listening_guide: str = ""
    connection: str = ""
    short_pitch: str = ""
    full_text: str = ""

    @classmethod
    def primary(cls, raw: dict[str, Any]) -> Self:
        """Build a primary pitch from a model's reply."""
        fields = {
            name: str(raw.get(name, "") or "")
            for name in ("hook", "context", "listening_guide", "connection")
        }
        return cls(**fields, full_text="\n\n".join(part for part in fields.values() if part))

    @classmethod
    def secondary(cls, raw: dict[str, Any]) -> Self:
        """Build a secondary pitch from a model's reply."""
        short = str(raw.get("short_pitch", "") or "")
        return cls(short_pitch=short, full_text=short)


class AlbumRecommendation(BaseModel):
    """One recommended album, with its pitch once one has been written.

    In discovery mode the album is not in the library, so `rating_key` and
    `track_rating_keys` are empty and the art comes from research instead.
    """

    rank: Rank
    album: str
    artist: str
    year: int | None = None
    rating_key: str | None = None
    track_rating_keys: list[str] = []
    art_url: str | None = None
    pitch: SommelierPitch = SommelierPitch()
    research_available: bool = False

    @property
    def ref(self) -> AlbumRef:
        """How this album is keyed in the research and facts lookups."""
        return AlbumRef(artist=self.artist, album=self.album)

    @classmethod
    def of_candidate(cls, candidate: AlbumCandidate, rank: Rank) -> Self:
        """Build from a library album, proxying art through the first track."""
        first_track = candidate.track_rating_keys[0] if candidate.track_rating_keys else None
        return cls(
            rank=rank,
            album=candidate.album,
            artist=candidate.album_artist,
            year=candidate.year,
            rating_key=candidate.parent_rating_key,
            track_rating_keys=candidate.track_rating_keys,
            art_url=f"/api/art/{first_track}" if first_track else None,
        )


class AlbumPreviewResponse(BaseModel):
    """How many albums one filter selection reaches.

    Counts only. What a round will cost is not predicted: the tokens it spends
    are reported by the provider once the calls have been made.
    """

    matching_albums: int
    albums_to_send: int

    @classmethod
    def of(cls, matching_albums: int, max_albums: int) -> Self:
        """What `matching_albums` of the library means for this selection."""
        return cls(
            matching_albums=matching_albums,
            albums_to_send=cls.capped(matching_albums, max_albums),
        )

    @staticmethod
    def capped(available: int, limit: int) -> int:
        """How many rows are actually sent; a limit of zero means all of them."""
        if available <= 0:
            return 0
        return min(available, limit) if limit > 0 else available


class RecommendGenerateResponse(BaseModel):
    """What one generation round produced, and what it cost.

    `research_warning` is set whenever a pitch could not be fully grounded, so
    the user is told which parts to take on trust.
    """

    recommendations: list[AlbumRecommendation]
    token_count: int = 0
    estimated_cost: float = 0.0
    research_warning: str | None = None

    @property
    def answered(self) -> dict[str, Any]:
        """The round as a trace shows it: which albums, and what they cost."""
        return {
            "recommendations": [
                f"{rec.rank}: {rec.album} by {rec.artist}" for rec in self.recommendations
            ],
            "token_count": self.token_count,
            "estimated_cost": self.estimated_cost,
            "research_warning": self.research_warning,
        }


class ResearchData(BaseModel):
    """External research fetched for grounding a pitch.

    `musicbrainz_id` doubles as the "this album exists" signal: without it the
    album could not be verified and discovery mode says so.
    """

    musicbrainz_id: str | None = None
    release_date: str | None = None
    label: str | None = None
    track_listing: list[str] = []
    credits: dict[str, str] = {}
    genre_tags: list[str] = []
    wikipedia_summary: str | None = None
    review_links: list[str] = []
    review_texts: list[str] = []
    cover_art_url: str | None = None
    earliest_release_mbid: str | None = None


class ExtractedFacts(BaseModel):
    """What the sources actually say about one album.

    Written by a model reading the research, and read back by the fact-checker.
    `track_listing` is the exception: it comes from MusicBrainz directly, so a
    pitch naming a track that is not on it is naming one that does not exist.
    """

    origin_story: str = ""
    personnel: list[str] = []
    musical_style: str = ""
    vocal_approach: str = ""
    cultural_context: str = ""
    track_highlights: str = ""
    common_misconceptions: str = ""
    source_coverage: str = ""
    track_listing: list[str] = []

    def to_text(self, include_track_listing: bool = True) -> str:
        """Format as a labelled block for a prompt."""
        labelled = [
            ("Origin", self.origin_story),
            ("Personnel", ", ".join(self.personnel)),
            ("Musical style", self.musical_style),
            ("Vocal approach", self.vocal_approach),
            ("Cultural context", self.cultural_context),
            ("Track highlights", self.track_highlights),
            ("Common misconceptions", self.common_misconceptions),
            ("Source coverage", self.source_coverage),
        ]
        parts = [f"- {label}: {value}" for label, value in labelled if value]
        if include_track_listing and self.track_listing:
            parts.append("- Track listing: " + ", ".join(self.track_listing))
        return "\n".join(parts)


class PitchIssue(BaseModel):
    """One factual claim the checker rejected, and what it should say."""

    claim: str
    problem: str
    correction: str


class PitchValidation(BaseModel):
    """Whether a pitch survived fact-checking."""

    valid: bool
    issues: list[PitchIssue] = []

    def corrections(self) -> str:
        """The issues as instructions for the rewrite."""
        return "\n".join(
            f'- WRONG: "{issue.claim}" → RIGHT: "{issue.correction}"' for issue in self.issues
        )


class FilterSuggestion(BaseModel):
    """Which genres and decades a prompt implies, and why."""

    genres: list[str] = []
    decades: list[str] = []
    reasoning: str = ""


class TasteProfile(BaseModel):
    """What the library says about the user, for recommending outside it.

    `owned` is both context and exclusion list: discovery must not recommend
    an album the user already has.
    """

    genre_distribution: dict[str, int] = {}
    decade_distribution: dict[str, int] = {}
    top_artists: list[str] = []
    total_albums: int = 0
    owned: list[AlbumRef] = []

    @classmethod
    def of(cls, candidates: list[AlbumCandidate], top_artists: int = 20) -> Self:
        """Aggregate every library album into one profile."""
        genres: dict[str, int] = {}
        decades: dict[str, int] = {}
        artists: dict[str, int] = {}

        for candidate in candidates:
            for genre in candidate.genres:
                genres[genre] = genres.get(genre, 0) + 1
            if candidate.decade:
                decades[candidate.decade] = decades.get(candidate.decade, 0) + 1
            artists[candidate.album_artist] = artists.get(candidate.album_artist, 0) + 1

        return cls(
            genre_distribution=genres,
            decade_distribution=decades,
            top_artists=cls._ranked(artists)[:top_artists],
            total_albums=len(candidates),
            owned=[
                AlbumRef(artist=candidate.album_artist, album=candidate.album)
                for candidate in candidates
            ],
        )

    @staticmethod
    def _ranked(counts: dict[str, int]) -> list[str]:
        """Keys ordered by count, highest first."""
        return sorted(counts, key=lambda name: counts[name], reverse=True)

    def owned_keys(self) -> set[str]:
        """Every owned album's key, for filtering what the model returns."""
        return {ref.key for ref in self.owned}

    def summary(self, genres: int = 10, decades: int = 5, artists: int = 10) -> str:
        """The profile as the model reads it."""
        return (
            f"Top genres: {', '.join(self._ranked(self.genre_distribution)[:genres])}\n"
            f"Top decades: {', '.join(self._ranked(self.decade_distribution)[:decades])}\n"
            f"Top artists: {', '.join(self.top_artists[:artists])}\n"
            f"Library size: {self.total_albums} albums"
        )


class RecommendSession(BaseModel):
    """One user's recommendation flow, held in memory between requests.

    `previously_recommended` is what "Show me another" excludes; the token and
    cost fields accumulate over a single generation round and are reset at the
    start of the next.
    """

    mode: Mode = "library"
    prompt: str = ""
    filters: dict[str, list[str]] = {}
    questions: list[ClarifyingQuestion] = []
    answers: AnswerSet = AnswerSet()
    album_candidates: list[AlbumCandidate] = []
    familiarity_pref: FamiliarityPreference = "any"
    previously_recommended: list[AlbumRef] = Field(default_factory=list)
    total_tokens: int = 0
    total_cost: float = 0.0
