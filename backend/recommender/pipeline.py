"""The recommendation pipeline the application talks through.

`RecommendationPipeline` owns the session store and hands out the three stages
of a round bound to the session paying for them, so a caller names a session
once rather than threading a metered client through every call. Entry points:
`pipeline_store`.

Every call reached from here is synchronous and spends real tokens. Call them
from an endpoint through `asyncio.to_thread`.
"""

import logging
import threading

from pydantic import BaseModel, ConfigDict, Field

from backend.llm import LLMClient, LLMNotConfigured, client_store
from backend.recommender.calls import NO_SESSION, MeteredClient
from backend.recommender.facts import Facts
from backend.recommender.pitches import Pitches
from backend.recommender.selection import Selection
from backend.recommender.sessions import SessionStore

logger = logging.getLogger(__name__)


class RoundStages(BaseModel):
    """The three stages of one round, every call charged to the same session."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    selection: Selection
    facts: Facts
    pitches: Pitches


class RecommendationPipeline(BaseModel):
    """One LLM client, the sessions running against it, and the stages between."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client: LLMClient
    # A factory, not a shared default: pydantic deep-copies a model default, and
    # SessionStore holds a threading.Lock, which cannot be copied.
    sessions: SessionStore = Field(default_factory=SessionStore)

    def stages(self, session_id: str = NO_SESSION) -> RoundStages:
        """The stages of a round, spending against `session_id`.

        The default runs ahead of any session -- what it costs is logged but
        attributed to nobody, which is what filter suggestion needs.
        """
        call = MeteredClient(client=self.client, sessions=self.sessions, session_id=session_id)
        return RoundStages(
            selection=Selection(call=call), facts=Facts(call=call), pitches=Pitches(call=call)
        )


class PipelineStore:
    """Holds the pipeline, rebuilding it when the LLM client changes.

    A settings change replaces the LLM client, and a pipeline built on the old
    one would keep spending against it. The rebuild carries the sessions over,
    so a user mid-flow does not lose their questions.

    A plain class, not a model: its methods are depended on directly by the
    routes, and a bound method of an unfrozen pydantic model is unhashable.
    """

    def __init__(self) -> None:
        self.pipeline: RecommendationPipeline | None = None
        self._lock = threading.Lock()

    def available(self) -> RecommendationPipeline | None:
        """The pipeline for the configured provider, or None when there is none.

        For a caller that degrades rather than failing.
        """
        return self.for_client(client_store.get())

    def require(self) -> RecommendationPipeline:
        """The pipeline for the configured provider.

        Raises:
            LLMNotConfigured: If no provider has been configured yet
        """
        built = self.available()
        if built is None:
            raise LLMNotConfigured("LLM client not configured. Set a provider in Settings.")
        return built

    def for_client(self, client: LLMClient | None) -> RecommendationPipeline | None:
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
