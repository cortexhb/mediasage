"""Tests for the recommendation sessions held between requests."""

import uuid

from backend.recommender.models import (
    AlbumCandidate,
    AlbumRef,
    AnswerSet,
    ClarifyingQuestion,
    RecommendSession,
)
from backend.recommender.sessions import SessionStore


def backdate(store: SessionStore, session_id: str, seconds: float) -> None:
    """Age one session, to reach code that only runs on an old entry."""
    session, touched = store._sessions[session_id]
    store._sessions[session_id] = (session, touched - seconds)


class TestLifecycle:
    def test_create_and_get(self, sessions):
        session_id = sessions.create(RecommendSession(prompt="jazz recs"))

        assert uuid.UUID(session_id).version == 4
        assert sessions.get(session_id).prompt == "jazz recs"

    def test_unknown_id_returns_none(self, sessions):
        assert sessions.get("does-not-exist") is None

    def test_delete(self, sessions):
        session_id = sessions.create(RecommendSession())
        sessions.delete(session_id)
        assert sessions.get(session_id) is None

    def test_deleting_twice_is_not_an_error(self, sessions):
        sessions.delete("never-existed")

    def test_expiry(self, sessions, limits):
        session_id = sessions.create(RecommendSession(prompt="old"))
        backdate(sessions, session_id, limits.session_expiry + 1)

        assert sessions.get(session_id) is None

    def test_a_read_keeps_a_session_alive(self, sessions, limits):
        """An active flow must not expire out from under a slow request."""
        session_id = sessions.create(RecommendSession())
        backdate(sessions, session_id, limits.session_expiry - 1)

        sessions.get(session_id)
        backdate(sessions, session_id, limits.session_expiry - 1)

        assert sessions.get(session_id) is not None

    def test_eviction_over_the_cap(self, sessions, limits):
        for index in range(limits.max_sessions + 5):
            sessions.create(RecommendSession(prompt=f"session {index}"))

        assert len(sessions._sessions) == limits.max_sessions

    def test_eviction_drops_the_oldest_first(self, sessions, limits):
        oldest = sessions.create(RecommendSession(prompt="first"))
        backdate(sessions, oldest, 60)
        newest = sessions.create(RecommendSession(prompt="second"))
        for _ in range(limits.max_sessions - 1):
            sessions.create(RecommendSession())

        assert sessions.get(oldest) is None
        assert sessions.get(newest) is not None

    def test_adopt_carries_live_flows_over(self, sessions):
        session_id = sessions.create(RecommendSession(prompt="migrated"))

        rebuilt = SessionStore()
        rebuilt.adopt(sessions)

        carried = rebuilt.get(session_id)
        assert carried is not None
        assert carried.prompt == "migrated"


class TestEdits:
    def test_editing_an_unknown_session_is_a_no_op(self, sessions):
        sessions.set_answers("gone", AnswerSet(answers=["calm"]))

    def test_set_questions(self, sessions):
        session_id = sessions.create(RecommendSession())
        question = ClarifyingQuestion(question_text="How loud?", options=["a"], dimension="energy")

        sessions.set_questions(session_id, [question])

        assert sessions.get(session_id).questions == [question]

    def test_set_answers(self, sessions):
        session_id = sessions.create(RecommendSession())

        sessions.set_answers(session_id, AnswerSet(answers=["option_a", None], texts=["Rock", ""]))

        answers = sessions.get(session_id).answers
        assert answers.answers == ["option_a", None]
        assert answers.texts == ["Rock", ""]

    def test_start_round_resets_the_cost(self, sessions):
        session_id = sessions.create(
            RecommendSession(prompt="test", total_tokens=500, total_cost=0.05)
        )

        sessions.start_round(session_id, "library", {}, "any", [])

        assert sessions.spend(session_id) == (0, 0.0)

    def test_start_round_leaves_the_prompt_alone(self, sessions):
        """A "Show me another" round is the same request, asked again."""
        session_id = sessions.create(RecommendSession())
        sessions.start_round(session_id, "library", {}, "any", [])
        sessions.edit(session_id, lambda s: setattr(s, "prompt", "kept"))

        sessions.start_round(session_id, "discovery", {"genres": ["Rock"]}, "comfort", [])

        session = sessions.get(session_id)
        assert session.mode == "discovery"
        assert session.familiarity_pref == "comfort"
        assert session.prompt == "kept"

    def test_start_round_replaces_the_candidate_pool(self, sessions):
        session_id = sessions.create(RecommendSession())
        sessions.start_round(session_id, "library", {}, "any", [AlbumCandidate(artist="Band", album_artist="Band", album="Album", parent_rating_key="1")])

        sessions.start_round(session_id, "library", {}, "any", [])

        assert sessions.get(session_id).album_candidates == []

    def test_add_spend_accumulates(self, sessions):
        session_id = sessions.create(RecommendSession())

        sessions.add_spend(session_id, 100, 0.01)
        sessions.add_spend(session_id, 50, 0.02)

        tokens, cost = sessions.spend(session_id)
        assert tokens == 150
        assert cost == 0.03

    def test_spend_of_an_unknown_session_is_zero(self, sessions):
        """A cost line for an expired session must not fail the request."""
        assert sessions.spend("gone") == (0, 0.0)


class TestRemember:
    def test_remembers_what_was_shown(self, sessions):
        session_id = sessions.create(RecommendSession())

        sessions.remember(session_id, [AlbumRef(artist="artist1", album="album1")])

        assert sessions.get(session_id).previously_recommended[0].album == "album1"

    def test_does_not_repeat_an_album(self, sessions):
        session_id = sessions.create(RecommendSession())
        ref = AlbumRef(artist="artist1", album="album1")

        sessions.remember(session_id, [ref])
        sessions.remember(session_id, [ref])

        assert len(sessions.get(session_id).previously_recommended) == 1

    def test_matches_on_the_folded_key(self, sessions):
        session_id = sessions.create(RecommendSession())

        sessions.remember(session_id, [AlbumRef(artist="Artist1", album="Album1")])
        sessions.remember(session_id, [AlbumRef(artist="artist1", album="album1")])

        assert len(sessions.get(session_id).previously_recommended) == 1

    def test_capped_at_the_recent_limit(self, sessions, limits):
        session_id = sessions.create(RecommendSession())
        overflow = limits.recent_limit + 5

        sessions.remember(
            session_id,
            [AlbumRef(artist=f"artist{i}", album=f"album{i}") for i in range(overflow)],
        )

        remembered = sessions.get(session_id).previously_recommended
        assert len(remembered) == limits.recent_limit
        assert remembered[-1].album == f"album{overflow - 1}"
