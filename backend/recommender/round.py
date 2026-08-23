"""One generation round, from a filled-in session to three pitched albums.

The caller resolves what the round needs, `RecommendationRound.run` does the
work and reports each step as it starts one. Everything between -- selection,
research, grounding, the pitch and its fact-check -- lives here rather than in
the endpoint, so the flow can be read and tested without an HTTP client.

`save` puts a finished round into history, as `PlaylistGeneration.save` does
for a playlist: the same store, and the same refusal to raise over it.

Every stage after selection is best-effort: research, fact extraction and
validation each degrade to a warning on the result rather than losing the
albums that were already picked. Selection is the exception -- with no albums
there is nothing to show.
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from typing import Any, Final
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field

from backend import library
from backend.library import AlbumCandidate, AlbumFamiliarity
from backend.recommender.models import (
    AlbumRecommendation,
    AlbumRef,
    AnswerSet,
    ExtractedFacts,
    FamiliarityPreference,
    Mode,
    RecommendGenerateResponse,
    ResearchData,
    TasteProfile,
)
from backend.recommender.pipeline import RecommendationPipeline
from backend.results import Result, results_store

logger = logging.getLogger(__name__)

# What the user is told while each stage runs.
STEPS: Final[dict[str, str]] = {
    "selecting_library": "Choosing albums from your library...",
    "selecting_discovery": "Finding albums to recommend...",
    "researching_primary": "Researching an album...",
    "researching_secondary": "Looking up additional picks...",
    "extracting_facts": "Analyzing research sources...",
    "writing": "Writing the pitch...",
    "validating": "Fact-checking the pitch...",
    "rewriting": "Refining the pitch...",
}

# Shown when a pitch could not be held to a source. Each names what is unsure.
NO_RESEARCH: Final = (
    "Research was unavailable — factual details could not be verified and may be approximate."
)
PRIMARY_RESEARCH_FAILED: Final = (
    "Research was unavailable for the primary album — factual details could not be "
    "verified and may be approximate."
)
NOT_IN_MUSICBRAINZ: Final = (
    "This album could not be verified in MusicBrainz — details may be approximate."
)
FAILED_VALIDATION: Final = (
    "The primary recommendation could not be fully verified against available sources."
)
STILL_UNVERIFIED: Final = "Some details could not be fully verified against available sources."

# Raised as a ValueError so the endpoint can tell a message meant for the user
# from an internal failure it has to sanitise.
NO_ALBUMS: Final = "No matching albums found. Try broadening your prompt or adjusting filters."


class Step(BaseModel):
    """One stage of the round, reported as it starts."""

    model_config = ConfigDict(frozen=True)

    step: str
    message: str


class RoundInputs(BaseModel):
    """Everything one round needs, resolved before it starts.

    Snapshotted by the caller rather than read from the session as the round
    runs: a concurrent "Show me another" would otherwise mutate the session
    mid-flight.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id: str
    prompt: str
    mode: Mode = "library"
    answers: AnswerSet = Field(default_factory=AnswerSet)
    familiarity_pref: FamiliarityPreference = "any"
    candidates: list[AlbumCandidate] = Field(default_factory=list)
    profile: TasteProfile = Field(default_factory=TasteProfile)
    already_shown: list[AlbumRef] = Field(default_factory=list)
    # Owned albums listed in the discovery prompt; 0 takes the configured cap.
    max_exclusion_albums: int = 0

    @property
    def is_discovery(self) -> bool:
        return self.mode == "discovery"


class RecommendationRound:
    """The stages of one round, over one pipeline and one research client.

    Not a pydantic model: it holds a research client whose type this package
    must not import, and it carries the mutable state of a single run.
    """

    def __init__(
        self,
        pipeline: RecommendationPipeline,
        research_client: Any,
        inputs: RoundInputs,
        abandoned: Callable[[], Awaitable[bool]] | None = None,
    ) -> None:
        """
        Args:
            pipeline: The session store and the stages, over the LLM this round spends
            research_client: `AlbumResearch`, for MusicBrainz, Wikipedia and reviews
            inputs: What the request resolved to
            abandoned: Asked between stages; True stops the round early
        """
        self.pipeline = pipeline
        self.stages = pipeline.stages(inputs.session_id)
        self.research_client = research_client
        self.inputs = inputs
        self.abandoned = abandoned
        self.research: dict[str, ResearchData] = {}
        self.facts: dict[str, ExtractedFacts] = {}
        self.warning: str | None = None

    async def run(self) -> AsyncIterator[Step | RecommendGenerateResponse]:
        """Work the round, reporting each stage and finally the result.

        Raises:
            ValueError: With a message meant for the user
        """
        yield self._step("selecting_discovery" if self.inputs.is_discovery else "selecting_library")
        familiarity = await self._familiarity()
        recommendations = await self._select(familiarity)
        if not recommendations:
            raise ValueError(NO_ALBUMS)

        primary = next((rec for rec in recommendations if rec.rank == "primary"), None)
        secondaries = [rec for rec in recommendations if rec.rank == "secondary"]

        if await self._stop():
            return
        yield self._step("researching_primary")
        if primary is not None:
            await self._research_primary(primary)

        if await self._stop():
            return
        yield self._step("researching_secondary")
        for secondary in secondaries:
            await self._research_secondary(secondary)

        if primary is not None and primary.ref.key in self.research:
            yield self._step("extracting_facts")
            await self._extract(primary)

        if await self._stop():
            return
        yield self._step("writing")
        recommendations = await self._write(recommendations, familiarity)

        if await self._stop():
            return
        if primary is not None and primary.ref.key in self.facts:
            async for step in self._check(primary):
                yield step

        if not self.research:
            self.warning = NO_RESEARCH

        tokens, cost = self.pipeline.sessions.spend(self.inputs.session_id)
        logger.info(
            "recommend.round | session=%s researched=%d facts=%d warned=%s",
            self.inputs.session_id,
            len(self.research),
            len(self.facts),
            self.warning is not None,
        )
        yield RecommendGenerateResponse(
            recommendations=recommendations,
            token_count=tokens,
            estimated_cost=cost,
            research_warning=self.warning,
        )

    def save(self, result: RecommendGenerateResponse) -> str | None:
        """Record the round in history, or None when that failed.

        History is a convenience: losing it must not lose the albums the user
        is looking at, so nothing here is allowed to raise.
        """
        primary = next((rec for rec in result.recommendations if rec.rank == "primary"), None)
        try:
            return results_store.save(
                Result(
                    type="album_recommendation",
                    title=(
                        f"{primary.album} by {primary.artist}"
                        if primary
                        else "Album Recommendation"
                    ),
                    prompt=self.inputs.prompt,
                    snapshot=result.model_dump(mode="json"),
                    track_count=len(result.recommendations),
                    artist=primary.artist if primary else None,
                    # A discovery pick is not in the library: no art key.
                    art_rating_key=(
                        primary.track_rating_keys[0]
                        if primary and primary.track_rating_keys
                        else None
                    ),
                    subtitle=(
                        primary.pitch.hook if primary and primary.pitch.hook else self.inputs.prompt
                    ),
                )
            )
        except Exception as err:
            logger.warning("Failed to save recommendation result: %s", err)
            return None

    # -- stages ----------------------------------------------------------

    async def _familiarity(self) -> dict[str, AlbumFamiliarity]:
        """How much of each candidate has been played, when that matters.

        Only read for a library round that asked for it: it is one query per
        round, and discovery has nothing in the library to have played. Empty
        when it was not asked for or the query failed -- an unknown play count
        and a zero one shape the prompt the same way.
        """
        if self.inputs.familiarity_pref == "any" or self.inputs.is_discovery:
            return {}

        keys = [
            candidate.parent_rating_key
            for candidate in self.inputs.candidates
            if candidate.parent_rating_key
        ]
        if not keys:
            return {}

        try:
            return await asyncio.to_thread(library.album_cache.familiarity, keys)
        except Exception as err:
            logger.warning("Familiarity query failed: %s", err)
            return {}

    async def _select(
        self, familiarity: Mapping[str, AlbumFamiliarity]
    ) -> list[AlbumRecommendation]:
        """Pick the albums, from the library or from outside it."""
        if self.inputs.is_discovery:
            return await asyncio.to_thread(
                self.stages.selection.select_discovery_albums,
                prompt=self.inputs.prompt,
                answers=self.inputs.answers,
                profile=self.inputs.profile,
                already_shown=self.inputs.already_shown,
                max_exclusion_albums=self.inputs.max_exclusion_albums,
            )

        return await asyncio.to_thread(
            self.stages.selection.select_albums,
            prompt=self.inputs.prompt,
            answers=self.inputs.answers,
            candidates=self.inputs.candidates,
            familiarity_pref=self.inputs.familiarity_pref,
            familiarity=familiarity,
            already_shown=self.inputs.already_shown,
        )

    async def _research_primary(self, primary: AlbumRecommendation) -> None:
        """Full research for the album the user reads in full.

        A discovery pick is also checked against what was found: a model can
        name an album that exists and is nothing like the request.
        """
        try:
            found = await self.research_client.of_album(primary.ref, full=True, year=primary.year)
        except Exception as err:
            logger.warning("Primary research failed: %s", err)
            self.warning = PRIMARY_RESEARCH_FAILED
            return

        if not found.musicbrainz_id:
            if self.inputs.is_discovery:
                logger.warning("Discovery album not in MusicBrainz: %s", primary.ref)
                self.warning = NOT_IN_MUSICBRAINZ
            return

        self._keep(primary, found)

        if self.inputs.is_discovery:
            valid = await asyncio.to_thread(
                self.stages.facts.matches_request,
                primary,
                found,
                self.inputs.prompt,
            )
            if not valid:
                logger.info("Primary discovery album failed validation")
                self.warning = FAILED_VALIDATION

        await self._cover_art(primary, found)

    async def _research_secondary(self, secondary: AlbumRecommendation) -> None:
        """Light research for a pick shown as one line: art, year, label."""
        try:
            found = await self.research_client.of_album(
                secondary.ref, full=False, year=secondary.year
            )
        except Exception as err:
            logger.warning("Secondary research failed for %s: %s", secondary.album, err)
            return

        if found.musicbrainz_id:
            self._keep(secondary, found)
            await self._cover_art(secondary, found)

    async def _extract(self, primary: AlbumRecommendation) -> None:
        """Read the primary's research into facts the pitch is held to."""
        try:
            self.facts[primary.ref.key] = await asyncio.to_thread(
                self.stages.facts.extract,
                ref=primary.ref,
                research=self.research[primary.ref.key],
            )
        except Exception as err:
            logger.warning("Fact extraction failed: %s", err)

    async def _write(
        self,
        recommendations: list[AlbumRecommendation],
        familiarity: Mapping[str, AlbumFamiliarity],
    ) -> list[AlbumRecommendation]:
        """Write every pitch, grounded in whatever was found."""
        return await asyncio.to_thread(
            self.stages.pitches.write,
            recommendations=recommendations,
            prompt=self.inputs.prompt,
            answers=self.inputs.answers,
            research=self.research,
            facts=self.facts,
            familiarity_pref=self.inputs.familiarity_pref,
            familiarity=familiarity,
        )

    async def _check(self, primary: AlbumRecommendation) -> AsyncIterator[Step]:
        """Fact-check the primary pitch, rewriting it once if it fails.

        Only once: a pitch that is still wrong after a rewrite is shown with a
        warning rather than rewritten again, which costs tokens and rarely
        converges.
        """
        facts = self.facts[primary.ref.key]
        yield self._step("validating")

        try:
            validation = await asyncio.to_thread(
                self.stages.pitches.fact_check,
                pitch=primary.pitch,
                facts=facts,
            )
            if validation.valid:
                return

            logger.info("Pitch validation found %d issues, rewriting", len(validation.issues))
            yield self._step("rewriting")
            await asyncio.to_thread(
                self.stages.pitches.rewrite,
                rec=primary,
                facts=facts,
                issues=validation,
                prompt=self.inputs.prompt,
                answers=self.inputs.answers,
            )

            rechecked = await asyncio.to_thread(
                self.stages.pitches.fact_check,
                pitch=primary.pitch,
                facts=facts,
            )
            if not rechecked.valid:
                logger.warning("Pitch still has %d issues after rewrite", len(rechecked.issues))
                self.warning = self.warning or STILL_UNVERIFIED
        except Exception as err:
            logger.warning("Pitch validation failed: %s", err)

    # -- helpers ---------------------------------------------------------

    def _step(self, name: str) -> Step:
        return Step(step=name, message=STEPS[name])

    async def _stop(self) -> bool:
        """Whether the caller has gone away, so the round can stop spending."""
        return await self.abandoned() if self.abandoned else False

    def _keep(self, rec: AlbumRecommendation, found: ResearchData) -> None:
        """Record research against an album and correct its year from it.

        Plex often carries a reissue's year; MusicBrainz has the original.
        """
        self.research[rec.ref.key] = found
        rec.research_available = True

        if found.release_date and len(found.release_date) >= 4:
            try:
                year = int(found.release_date[:4])
            except ValueError:
                return
            if rec.year != year:
                logger.info("Year override: Plex=%s MusicBrainz=%s for %s", rec.year, year, rec.ref)
                rec.year = year

    async def _cover_art(self, rec: AlbumRecommendation, found: ResearchData) -> None:
        """Fall back to the Cover Art Archive when Plex has no art.

        Proxied rather than hotlinked, so the page never fetches from the
        archive directly.
        """
        if rec.art_url or not found.earliest_release_mbid:
            return
        art_url = await self.research_client.covers.front(
            found.earliest_release_mbid, found.musicbrainz_id
        )
        if art_url:
            rec.art_url = f"/api/external-art?url={quote(art_url, safe='')}"
