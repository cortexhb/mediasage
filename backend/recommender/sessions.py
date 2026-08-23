"""The recommendation sessions this process is holding.

A session carries a user through questions, generation, and any number of
"Show me another" rounds. It lives in memory only: losing one costs a repeated
round of questions, not data. Entry point: `SessionStore`.

Every read touches the session's timestamp, so an active flow is never expired
out from under the user mid-request.
"""

import logging
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from pydantic import BaseModel, ConfigDict, PrivateAttr

from backend.config.store import config_store
from backend.library import AlbumCandidate
from backend.recommender.models import (
    AlbumRef,
    AnswerSet,
    ClarifyingQuestion,
    FamiliarityPreference,
    Mode,
    RecommendSession,
)

logger = logging.getLogger(__name__)


class SessionStore(BaseModel):
    """Every live recommendation session, keyed by id.

    One lock guards the whole map: sessions are small, contention is a handful
    of concurrent users, and finer locking would buy nothing.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _sessions: dict[str, tuple[RecommendSession, float]] = PrivateAttr(default_factory=dict)
    _lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)

    def create(self, session: RecommendSession) -> str:
        """Store a new session and return the id it answers to.

        A whole uuid4, canonical form: nothing reads the id back apart from
        this map, and an insert here overwrites rather than reporting a clash.
        """
        with self._lock:
            session_id = str(uuid.uuid4())
            self._sessions[session_id] = (session, time.time())
            # Swept after the insert, not before: sweeping first would leave the
            # store holding one more than the cap until the next read.
            self._sweep()
            return session_id

    def get(self, session_id: str) -> RecommendSession | None:
        """One session, or None once it has expired or been deleted."""
        with self._lock:
            self._sweep()
            entry = self._sessions.get(session_id)
            if entry is None:
                return None
            session, _ = entry
            self._sessions[session_id] = (session, time.time())
            return session

    def delete(self, session_id: str) -> None:
        """Forget a session; deleting an unknown id is not an error."""
        with self._lock:
            self._sessions.pop(session_id, None)

    def adopt(self, other: SessionStore) -> None:
        """Take over another store's sessions, so a rebuild keeps live flows."""
        with other._lock, self._lock:
            self._sessions = dict(other._sessions)

    @contextmanager
    def _editing(self, session_id: str) -> Iterator[RecommendSession | None]:
        """Hold the lock over one session, touching its timestamp on the way out."""
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry is None:
                yield None
                return
            session, _ = entry
            yield session
            self._sessions[session_id] = (session, time.time())

    def edit(self, session_id: str, change: Callable[[RecommendSession], None]) -> None:
        """Apply `change` to one session, if it is still there."""
        with self._editing(session_id) as session:
            if session is not None:
                change(session)

    def set_questions(self, session_id: str, questions: list[ClarifyingQuestion]) -> None:
        """Record the questions the user is about to be asked."""
        self.edit(session_id, lambda session: setattr(session, "questions", questions))

    def set_answers(self, session_id: str, answers: AnswerSet) -> None:
        """Record what the user answered."""
        self.edit(session_id, lambda session: setattr(session, "answers", answers))

    def start_round(
        self,
        session_id: str,
        mode: Mode,
        filters: dict[str, list[str]],
        familiarity_pref: FamiliarityPreference,
        album_candidates: list[AlbumCandidate],
    ) -> None:
        """Set up one generation round, resetting the cost it will accrue."""
        def apply(session: RecommendSession) -> None:
            session.mode = mode
            session.filters = filters
            session.familiarity_pref = familiarity_pref
            session.album_candidates = album_candidates
            session.total_tokens = 0
            session.total_cost = 0.0

        self.edit(session_id, apply)

    def add_spend(self, session_id: str, tokens: int, cost: float) -> None:
        """Accumulate what one LLM call cost this round."""
        def apply(session: RecommendSession) -> None:
            session.total_tokens += tokens
            session.total_cost += cost

        self.edit(session_id, apply)

    def spend(self, session_id: str) -> tuple[int, float]:
        """Tokens and cost accumulated this round; zeros for an unknown session."""
        with self._editing(session_id) as session:
            return (session.total_tokens, session.total_cost) if session else (0, 0.0)

    def remember(self, session_id: str, shown: list[AlbumRef]) -> None:
        """Add albums to what the next round must not repeat."""
        limit = config_store.get().recommend.recent_limit

        def apply(session: RecommendSession) -> None:
            seen = {ref.key for ref in session.previously_recommended}
            for ref in shown:
                if ref.key not in seen:
                    seen.add(ref.key)
                    session.previously_recommended.append(ref)
            session.previously_recommended = session.previously_recommended[-limit:]

        self.edit(session_id, apply)

    def _sweep(self) -> None:
        """Drop expired sessions, then the oldest if still over the cap.

        The caller holds the lock.
        """
        limits = config_store.get().recommend
        now = time.time()
        for session_id in [
            key for key, (_, touched) in self._sessions.items()
            if now - touched > limits.session_expiry
        ]:
            del self._sessions[session_id]
            logger.info("Expired recommendation session %s", session_id)

        while len(self._sessions) > limits.max_sessions:
            oldest = min(self._sessions, key=lambda key: self._sessions[key][1])
            del self._sessions[oldest]
            logger.info("Evicted oldest recommendation session %s (over cap)", oldest)
