"""Tests for the pipeline facade and the store that rebuilds it."""

from unittest.mock import MagicMock

from backend.config import MediasageConfig
from backend.config.store import config_store
from backend.llm import LLMClient
from backend.recommender.calls import NO_SESSION, MeteredClient, as_dict, as_list
from backend.recommender.models import AnswerSet, RecommendSession
from backend.recommender.pipeline import PipelineStore, RecommendationPipeline
from tests.recommender.conftest import scripted_llm


class TestMeteredClient:
    def test_charges_the_session(self, sessions):
        session_id = sessions.create(RecommendSession())
        call = MeteredClient(client=scripted_llm({}), sessions=sessions, session_id=session_id)

        call.analyze("system", "prompt", "test_call")

        tokens, cost = sessions.spend(session_id)
        assert tokens == 150
        assert cost > 0

    def test_an_unpriced_provider_charges_tokens_but_no_cost(self, sessions, monkeypatch):
        """An unset price means the UI reports no cost rather than a wrong one."""
        monkeypatch.setattr(
            config_store,
            "config",
            MediasageConfig(llm={"provider": "anthropic", "context_window": 200000}),
        )
        session_id = sessions.create(RecommendSession())
        call = MeteredClient(client=scripted_llm({}), sessions=sessions, session_id=session_id)

        call.analyze("system", "prompt", "test_call")

        assert sessions.spend(session_id) == (150, 0.0)

    def test_a_call_outside_a_session_still_works(self, sessions):
        """Filter suggestion runs before a session exists."""
        call = MeteredClient(client=scripted_llm({"genres": []}), sessions=sessions)

        assert call.session_id == NO_SESSION
        assert call.generate("system", "prompt", "test_call") == {"genres": []}

    def test_hands_the_prompts_over_in_the_client_order(self, sessions):
        client = scripted_llm({})
        call = MeteredClient(client=client, sessions=sessions)

        call.analyze("the system prompt", "the user prompt", "test_call")

        assert client.analyze.call_args[0] == ("the user prompt", "the system prompt")


class TestReplyGuards:
    def test_a_list_passes_through(self):
        assert as_list([1, 2]) == [1, 2]

    def test_a_wrapped_array_is_unwrapped(self):
        """Models asked for a JSON array sometimes wrap it in an object."""
        assert as_list({"albums": [1, 2]}) == [1, 2]

    def test_a_lone_object_becomes_one_item(self):
        assert as_list({"artist": "A"}) == [{"artist": "A"}]

    def test_anything_else_is_empty(self):
        assert as_list("prose") == []
        assert as_list(None) == []

    def test_as_dict_rejects_a_non_object(self):
        assert as_dict(["a"]) == {}
        assert as_dict({"a": 1}) == {"a": 1}


class TestPipeline:
    def test_each_pipeline_gets_its_own_sessions(self):
        """A shared default would leak one user's flow into another's."""
        first = RecommendationPipeline(client=MagicMock(spec=LLMClient))
        second = RecommendationPipeline(client=MagicMock(spec=LLMClient))

        assert first.sessions is not second.sessions

    def test_a_stage_spends_against_the_session_it_was_given(self):
        pipeline = RecommendationPipeline(client=scripted_llm(["era", "tempo"]))
        session_id = pipeline.sessions.create(RecommendSession())

        pipeline.gap_analysis(session_id, "something nostalgic")

        assert pipeline.sessions.spend(session_id)[0] == 150

    def test_filter_suggestion_is_not_attributed(self, sessions):
        """It runs ahead of the session, so its cost is logged but not charged."""
        pipeline = RecommendationPipeline(client=scripted_llm({"genres": ["Rock"]}))
        session_id = pipeline.sessions.create(RecommendSession())

        pipeline.suggest_filters("test", ["Rock"], ["1990s"])

        assert pipeline.sessions.spend(session_id) == (0, 0.0)

    def test_write_pitches_reaches_the_stage(self):
        pipeline = RecommendationPipeline(client=scripted_llm([]))
        session_id = pipeline.sessions.create(RecommendSession())

        recs = pipeline.write_pitches(session_id, [], "test", AnswerSet())

        assert recs == []


class TestPipelineStore:
    def test_no_client_means_no_pipeline(self):
        assert PipelineStore().get(None) is None

    def test_builds_once_and_reuses(self):
        store = PipelineStore()
        client = MagicMock(spec=LLMClient)

        assert store.get(client) is store.get(client)

    def test_a_new_client_rebuilds(self):
        """A settings change replaces the client; the old one must stop being spent."""
        store = PipelineStore()
        first = store.get(MagicMock(spec=LLMClient))

        second = store.get(MagicMock(spec=LLMClient))

        assert second is not first
        assert second.client is not first.client

    def test_a_rebuild_carries_live_sessions_over(self):
        """A user mid-flow must not lose their questions to a settings save."""
        store = PipelineStore()
        first = store.get(MagicMock(spec=LLMClient))
        session_id = first.sessions.create(RecommendSession(prompt="mid-flow"))

        second = store.get(MagicMock(spec=LLMClient))

        assert second.sessions.get(session_id).prompt == "mid-flow"

    def test_dropping_the_client_reports_unavailable(self):
        store = PipelineStore()
        store.get(MagicMock(spec=LLMClient))

        assert store.get(None) is None
