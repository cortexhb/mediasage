"""Tests for the pipeline, its stages, and the store that rebuilds it."""

from unittest.mock import MagicMock

from backend.config import MediasageConfig
from backend.config.store import config_store
from backend.llm import LLMClient
from backend.recommender.calls import NO_SESSION, MeteredClient, Stage
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

        assert client.analyze.call_args[0][:2] == ("the user prompt", "the system prompt")


class TestTracedSession:
    """Tests for which id the calls group under in Langfuse."""

    def test_a_call_outside_a_session_groups_under_nothing(self, sessions):
        call = MeteredClient(client=scripted_llm({}), sessions=sessions)

        assert call.traced_session == ""

    def test_a_session_groups_under_itself(self, sessions):
        call = MeteredClient(client=scripted_llm({}), sessions=sessions, session_id="s-1")

        assert call.traced_session == "s-1"

    def test_the_flow_wins_over_the_session(self, sessions):
        """The playlist flow's questions open a session of their own."""
        call = MeteredClient(
            client=scripted_llm({}), sessions=sessions, session_id="s-1", flow_id="f-1"
        )

        assert call.traced_session == "f-1"

    def test_the_flow_reaches_the_client(self, sessions):
        client = scripted_llm({})
        call = MeteredClient(client=client, sessions=sessions, flow_id="f-1")

        call.generate("system", "prompt", "test_call")

        assert client.generate.call_args[0][2] == "f-1"


class TestStages:
    def test_the_flow_reaches_every_stage(self, sessions):
        """One flow id, so questions and generation share a session."""
        pipeline = RecommendationPipeline(client=scripted_llm({}), sessions=sessions)

        stages = pipeline.stages("s-1", "f-1")

        assert stages.selection.call.traced_session == "f-1"
        assert stages.facts.call.traced_session == "f-1"
        assert stages.pitches.call.traced_session == "f-1"

    def test_no_flow_leaves_the_session_in_charge(self, sessions):
        pipeline = RecommendationPipeline(client=scripted_llm({}), sessions=sessions)

        assert pipeline.stages("s-1").selection.call.traced_session == "s-1"


class TestReplyGuards:
    def test_a_list_passes_through(self):
        assert Stage.as_list([1, 2]) == [1, 2]

    def test_a_wrapped_array_is_unwrapped(self):
        """Models asked for a JSON array sometimes wrap it in an object."""
        assert Stage.as_list({"albums": [1, 2]}) == [1, 2]

    def test_a_lone_object_becomes_one_item(self):
        assert Stage.as_list({"artist": "A"}) == [{"artist": "A"}]

    def test_anything_else_is_empty(self):
        assert Stage.as_list("prose") == []
        assert Stage.as_list(None) == []

    def test_as_dict_rejects_a_non_object(self):
        assert Stage.as_dict(["a"]) == {}
        assert Stage.as_dict({"a": 1}) == {"a": 1}


class TestPipeline:
    def test_each_pipeline_gets_its_own_sessions(self):
        """A shared default would leak one user's flow into another's."""
        first = RecommendationPipeline(client=MagicMock(spec=LLMClient))
        second = RecommendationPipeline(client=MagicMock(spec=LLMClient))

        assert first.sessions is not second.sessions

    def test_a_stage_spends_against_the_session_it_was_given(self):
        pipeline = RecommendationPipeline(client=scripted_llm(["era", "tempo"]))
        session_id = pipeline.sessions.create(RecommendSession())

        pipeline.stages(session_id).selection.gap_analysis("something nostalgic")

        assert pipeline.sessions.spend(session_id)[0] == 150

    def test_a_stage_without_a_session_is_not_attributed(self, sessions):
        """Filter suggestion runs ahead of the session it would be charged to."""
        pipeline = RecommendationPipeline(client=scripted_llm({"genres": ["Rock"]}))
        session_id = pipeline.sessions.create(RecommendSession())

        pipeline.stages().selection.suggest_filters("test", ["Rock"], ["1990s"])

        assert pipeline.sessions.spend(session_id) == (0, 0.0)

    def test_all_three_stages_spend_through_the_one_client(self):
        """Two clients would charge the same session twice over."""
        pipeline = RecommendationPipeline(client=scripted_llm([]))
        stages = pipeline.stages("session-1")

        assert stages.selection.call is stages.facts.call is stages.pitches.call

    def test_the_pitch_stage_reaches_the_client(self):
        pipeline = RecommendationPipeline(client=scripted_llm([]))
        session_id = pipeline.sessions.create(RecommendSession())

        recs = pipeline.stages(session_id).pitches.write([], "test", AnswerSet())

        assert recs == []


class TestPipelineStore:
    def test_no_client_means_no_pipeline(self):
        assert PipelineStore().for_client(None) is None

    def test_builds_once_and_reuses(self):
        store = PipelineStore()
        client = MagicMock(spec=LLMClient)

        assert store.for_client(client) is store.for_client(client)

    def test_a_new_client_rebuilds(self):
        """A settings change replaces the client; the old one must stop being spent."""
        store = PipelineStore()
        first = store.for_client(MagicMock(spec=LLMClient))

        second = store.for_client(MagicMock(spec=LLMClient))

        assert first is not None
        assert second is not None
        assert second is not first
        assert second.client is not first.client

    def test_a_rebuild_carries_live_sessions_over(self):
        """A user mid-flow must not lose their questions to a settings save."""
        store = PipelineStore()
        first = store.for_client(MagicMock(spec=LLMClient))
        assert first is not None
        session_id = first.sessions.create(RecommendSession(prompt="mid-flow"))

        second = store.for_client(MagicMock(spec=LLMClient))

        assert second is not None
        carried = second.sessions.get(session_id)
        assert carried is not None
        assert carried.prompt == "mid-flow"

    def test_dropping_the_client_reports_unavailable(self):
        store = PipelineStore()
        store.for_client(MagicMock(spec=LLMClient))

        assert store.for_client(None) is None
