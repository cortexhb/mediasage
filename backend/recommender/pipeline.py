"""The recommendation pipeline the application talks through.

`RecommendationPipeline` is a facade: it owns the session store and binds each
stage to the session paying for it, so a caller passes a session id rather than
threading a metered client through every call. Entry points: `pipeline_store`.

Every method here is synchronous and spends real tokens. Call them from an
endpoint through `asyncio.to_thread`.
"""

import logging
import threading

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from backend.library import AlbumCandidate, AlbumFamiliarity
from backend.llm import LLMClient
from backend.recommender import facts as facts_module
from backend.recommender import pitches, selection
from backend.recommender.calls import MeteredClient
from backend.recommender.models import (
    AlbumRecommendation,
    AlbumRef,
    AnswerSet,
    ClarifyingQuestion,
    ExtractedFacts,
    FamiliarityPreference,
    FilterSuggestion,
    PitchValidation,
    ResearchData,
    SommelierPitch,
    TasteProfile,
)
from backend.recommender.sessions import SessionStore

logger = logging.getLogger(__name__)


class RecommendationPipeline(BaseModel):
    """One LLM client, the sessions running against it, and the stages between."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client: LLMClient
    # A factory, not a shared default: pydantic deep-copies a model default, and
    # SessionStore holds a threading.Lock, which cannot be copied.
    sessions: SessionStore = Field(default_factory=SessionStore)

    def _for(self, session_id: str) -> MeteredClient:
        """A client whose spend lands on `session_id`."""
        return MeteredClient(client=self.client, sessions=self.sessions, session_id=session_id)

    # -- before a session exists -----------------------------------------

    def suggest_filters(
        self, prompt: str, genres: list[str], decades: list[str]
    ) -> FilterSuggestion:
        """Narrow the library before the user is asked anything.

        Runs ahead of the session, so its cost is logged but not attributed.
        """
        return selection.suggest_filters(
            MeteredClient(client=self.client, sessions=self.sessions), prompt, genres, decades
        )

    # -- questions -------------------------------------------------------

    def gap_analysis(self, session_id: str, prompt: str) -> list[str]:
        """The dimensions worth asking about."""
        return selection.gap_analysis(self._for(session_id), prompt)

    def generate_questions(
        self, session_id: str, prompt: str, dimension_ids: list[str]
    ) -> list[ClarifyingQuestion]:
        """The questions to put to the user."""
        return selection.generate_questions(self._for(session_id), prompt, dimension_ids)

    # -- selection -------------------------------------------------------

    def select_albums(
        self,
        session_id: str,
        prompt: str,
        answers: AnswerSet,
        candidates: list[AlbumCandidate],
        familiarity_pref: FamiliarityPreference = "any",
        familiarity: dict[str, AlbumFamiliarity] | None = None,
        already_shown: list[AlbumRef] | None = None,
    ) -> list[AlbumRecommendation]:
        """Pick albums out of the user's own library."""
        return selection.select_albums(
            self._for(session_id), prompt, answers, candidates,
            familiarity_pref, familiarity, already_shown,
        )

    def select_discovery_albums(
        self,
        session_id: str,
        prompt: str,
        answers: AnswerSet,
        profile: TasteProfile,
        already_shown: list[AlbumRef] | None = None,
        max_exclusion_albums: int | None = None,
    ) -> list[AlbumRecommendation]:
        """Pick albums the user does not own."""
        return selection.select_discovery_albums(
            self._for(session_id), prompt, answers, profile,
            already_shown, max_exclusion_albums,
        )

    # -- grounding and pitches -------------------------------------------

    def extract_facts(
        self, session_id: str, ref: AlbumRef, research: ResearchData
    ) -> ExtractedFacts:
        """Read one album's research into labelled facts."""
        return facts_module.extract(self._for(session_id), ref, research)

    def validate_discovery_album(
        self, session_id: str, rec: AlbumRecommendation, research: ResearchData, prompt: str
    ) -> bool:
        """Whether a discovery pick fits what was asked for."""
        return facts_module.matches_request(self._for(session_id), rec, research, prompt)

    def write_pitches(
        self,
        session_id: str,
        recommendations: list[AlbumRecommendation],
        prompt: str,
        answers: AnswerSet,
        research: dict[str, ResearchData] | None = None,
        facts: dict[str, ExtractedFacts] | None = None,
        familiarity_pref: FamiliarityPreference = "any",
        familiarity: dict[str, AlbumFamiliarity] | None = None,
    ) -> list[AlbumRecommendation]:
        """Write a pitch for every recommendation."""
        return pitches.write(
            self._for(session_id), recommendations, prompt, answers,
            research, facts, familiarity_pref, familiarity,
        )

    def validate_pitch(
        self, session_id: str, pitch: SommelierPitch, facts: ExtractedFacts
    ) -> PitchValidation:
        """Fact-check a pitch against what the sources said."""
        return pitches.validate(self._for(session_id), pitch, facts)

    def rewrite_pitch(
        self,
        session_id: str,
        rec: AlbumRecommendation,
        facts: ExtractedFacts,
        issues: PitchValidation,
        prompt: str,
        answers: AnswerSet,
    ) -> None:
        """Rewrite a primary pitch around its corrections, in place."""
        pitches.rewrite(self._for(session_id), rec, facts, issues, prompt, answers)


class PipelineStore(BaseModel):
    """Holds the pipeline, rebuilding it when the LLM client changes.

    A settings change replaces the LLM client, and a pipeline built on the old
    one would keep spending against it. The rebuild carries the sessions over,
    so a user mid-flow does not lose their questions.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    pipeline: RecommendationPipeline | None = None

    _lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)

    def get(self, client: LLMClient | None) -> RecommendationPipeline | None:
        """The pipeline for `client`, built or rebuilt as needed.

        Returns None when no LLM provider is configured, which is what the
        endpoints report as unavailable.
        """
        if client is None:
            return None

        current = self.pipeline
        if current is not None and current.client is client:
            return current

        with self._lock:
            # Another request may have rebuilt it while this one waited; a
            # second rebuild here would strand the sessions it carried over.
            current = self.pipeline
            if current is not None and current.client is client:
                return current

            rebuilt = RecommendationPipeline(client=client)
            if current is not None:
                rebuilt.sessions.adopt(current.sessions)
            self.pipeline = rebuilt
            return rebuilt


# The single instance the application talks through.
pipeline_store = PipelineStore()
