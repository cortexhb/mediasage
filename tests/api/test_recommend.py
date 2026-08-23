"""Tests for ``/api/recommend`` -- the endpoints around the round."""

import uuid
from unittest.mock import MagicMock

import pytest

from backend.recommender import (
    AnswerSet,
    ClarifyingQuestion,
    FilterSuggestion,
    RecommendSession,
    SessionStore,
    pipeline_store,
)


@pytest.fixture
def pipeline(client):
    """A pipeline whose stages answer instantly, with a real session store."""
    built = MagicMock()
    built.sessions = SessionStore()
    # `stages` returns itself, so a test scripts a stage without naming a session.
    stages = built.stages
    stages.return_value = stages
    stages.selection.gap_analysis.return_value = ["energy", "era"]
    stages.selection.generate_questions.return_value = [
        ClarifyingQuestion(question_text="How loud?", options=["Quiet"], dimension="energy")
    ]
    stages.selection.suggest_filters.return_value = FilterSuggestion(
        genres=["Rock"], decades=["1990s"]
    )
    client.app.dependency_overrides[pipeline_store.require] = lambda: built
    client.app.dependency_overrides[pipeline_store.available] = lambda: built
    yield built
    client.app.dependency_overrides.clear()


class TestQuestions:
    def test_returns_questions_and_a_session(self, client, pipeline):
        response = client.post("/api/recommend/questions", json={"prompt": "something calm"})

        assert response.status_code == 200
        data = response.json()
        assert uuid.UUID(data["session_id"]).version == 4
        assert data["questions"][0]["question_text"] == "How loud?"

    def test_the_session_holds_the_questions(self, client, pipeline):
        session_id = client.post(
            "/api/recommend/questions", json={"prompt": "test"}
        ).json()["session_id"]

        assert pipeline.sessions.get(session_id).questions[0].dimension == "energy"

    def test_a_failure_leaves_no_stranded_session(self, client, pipeline):
        """A session with no questions would strand the user on an empty form."""
        pipeline.stages.selection.gap_analysis.side_effect = RuntimeError("model refused")

        response = client.post("/api/recommend/questions", json={"prompt": "test"})

        assert response.status_code == 500
        assert pipeline.sessions._sessions == {}


class TestSwitchMode:
    def test_carries_the_answers_over(self, client, pipeline):
        session_id = pipeline.sessions.create(
            RecommendSession(prompt="test", previously_recommended=[])
        )
        pipeline.sessions.set_answers(session_id, AnswerSet(answers=["calm"]))

        response = client.post(
            "/api/recommend/switch-mode",
            json={"session_id": session_id, "mode": "discovery"},
        )

        switched = response.json()["session_id"]
        assert switched != session_id
        assert pipeline.sessions.get(switched).answers.answers == ["calm"]
        assert pipeline.sessions.get(switched).mode == "discovery"

    def test_the_old_session_is_dropped(self, client, pipeline):
        session_id = pipeline.sessions.create(RecommendSession(prompt="test"))

        client.post(
            "/api/recommend/switch-mode",
            json={"session_id": session_id, "mode": "discovery"},
        )

        assert pipeline.sessions.get(session_id) is None

    def test_switching_to_the_same_mode_is_a_no_op(self, client, pipeline):
        session_id = pipeline.sessions.create(RecommendSession(prompt="test", mode="library"))

        response = client.post(
            "/api/recommend/switch-mode",
            json={"session_id": session_id, "mode": "library"},
        )

        assert response.json()["session_id"] == session_id

    def test_an_expired_session_is_404(self, client, pipeline):
        response = client.post(
            "/api/recommend/switch-mode",
            json={"session_id": "gone", "mode": "discovery"},
        )

        assert response.status_code == 404


class TestAnalyzePrompt:
    def test_narrows_the_filters(self, client, pipeline):
        response = client.post(
            "/api/recommend/analyze-prompt",
            json={"prompt": "90s rock", "genres": ["Rock", "Jazz"], "decades": ["1990s"]},
        )

        assert response.json()["genres"] == ["Rock"]

    def test_a_failure_returns_everything(self, client, pipeline):
        """Not worth blocking on: the user narrows them by hand."""
        pipeline.stages.selection.suggest_filters.side_effect = RuntimeError("model refused")

        response = client.post(
            "/api/recommend/analyze-prompt",
            json={"prompt": "test", "genres": ["Rock", "Jazz"], "decades": ["1990s"]},
        )

        assert response.status_code == 200
        assert response.json()["genres"] == ["Rock", "Jazz"]


class TestGenerate:
    def test_an_expired_session_is_404(self, client, pipeline):
        response = client.post(
            "/api/recommend/generate", json={"session_id": "gone", "answers": []}
        )

        assert response.status_code == 404

    def test_an_empty_cache_says_to_sync(self, client, pipeline, temp_db):
        session_id = pipeline.sessions.create(RecommendSession(prompt="test"))

        response = client.post(
            "/api/recommend/generate", json={"session_id": session_id, "answers": []}
        )

        assert response.status_code == 400
        assert "sync" in response.json()["detail"].lower()

    def test_discovery_says_why_it_needs_the_library(self, client, pipeline, temp_db):
        session_id = pipeline.sessions.create(RecommendSession(prompt="test"))

        response = client.post(
            "/api/recommend/generate",
            json={"session_id": session_id, "answers": [], "mode": "discovery"},
        )

        assert response.status_code == 400
        assert "taste profile" in response.json()["detail"]

    def test_a_negative_album_cap_is_rejected(self, client, pipeline):
        response = client.post(
            "/api/recommend/generate",
            json={"session_id": "unknown", "answers": [], "max_albums": -1},
        )

        assert response.status_code == 422


class TestPreview:
    def test_reports_zero_for_an_unsynced_library(self, client, temp_db):
        response = client.get("/api/recommend/albums/preview")

        assert response.status_code == 200
        assert response.json()["matching_albums"] == 0
