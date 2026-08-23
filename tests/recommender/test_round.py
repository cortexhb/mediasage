"""Tests for one generation round: what it reports, and what it survives."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.recommender import round as round_module
from backend.recommender.models import (
    AlbumRecommendation,
    AlbumRef,
    ExtractedFacts,
    PitchIssue,
    PitchValidation,
    RecommendGenerateResponse,
    RecommendSession,
    ResearchData,
    SommelierPitch,
    TasteProfile,
)
from backend.recommender.round import RecommendationRound, RoundInputs, Step
from backend.recommender.sessions import SessionStore
from backend.results import Result
from tests.recommender.conftest import candidate


def picks() -> list[AlbumRecommendation]:
    """One primary and one secondary, as selection returns them."""
    return [
        AlbumRecommendation(rank="primary", artist="Sigur Rós", album="Ágætis byrjun", year=2001),
        AlbumRecommendation(rank="secondary", artist="Slint", album="Spiderland"),
    ]


def fake_pipeline(**overrides) -> MagicMock:
    """A pipeline whose stages answer instantly, with a real session store.

    `pipeline.stages` returns itself, so a test scripts a stage and reads the
    calls the round made off the one object regardless of session id.
    """
    pipeline = MagicMock()
    pipeline.sessions = SessionStore()
    stages = pipeline.stages
    stages.return_value = stages
    stages.selection.select_albums.return_value = overrides.pop("selected", picks())
    stages.selection.select_discovery_albums.return_value = overrides.pop("discovered", picks())
    stages.facts.extract.return_value = ExtractedFacts(origin_story="Recorded in Reykjavik")
    stages.facts.matches_request.return_value = True
    stages.pitches.fact_check.return_value = PitchValidation(valid=True)
    stages.pitches.write.side_effect = lambda **kwargs: kwargs["recommendations"]
    for name, value in overrides.items():
        getattr(stages, name).return_value = value
    return pipeline


def fake_research(**overrides) -> MagicMock:
    """A research client that finds one album by default."""
    client = MagicMock()
    client.of_album = AsyncMock(
        return_value=overrides.pop("found", ResearchData(musicbrainz_id="mbid-1"))
    )
    client.covers.front = AsyncMock(return_value=overrides.pop("art", None))
    return client


def inputs(**overrides) -> RoundInputs:
    fields = {
        "session_id": "test-session",
        "prompt": "something atmospheric",
        "candidates": [candidate(f"Band{i}", f"Album{i}") for i in range(5)],
    }
    fields.update(overrides)
    return RoundInputs(**fields)


async def collect(
    round_: RecommendationRound,
) -> tuple[list[Step], RecommendGenerateResponse | None]:
    """Drain a round into its steps and its result."""
    steps: list[Step] = []
    result = None
    async for update in round_.run():
        if isinstance(update, Step):
            steps.append(update)
        else:
            result = update
    return steps, result


async def result_of(round_: RecommendationRound) -> RecommendGenerateResponse:
    """Drain a round that is expected to finish, returning what it yielded."""
    _, result = await collect(round_)
    assert result is not None
    return result


class TestProgress:
    async def test_reports_every_stage_in_order(self):
        pipeline = fake_pipeline()
        round_ = RecommendationRound(pipeline, fake_research(), inputs())

        steps, result = await collect(round_)

        assert [step.step for step in steps] == [
            "selecting_library",
            "researching_primary",
            "researching_secondary",
            "extracting_facts",
            "writing",
            "validating",
        ]
        assert result is not None

    async def test_discovery_says_it_is_discovering(self):
        round_ = RecommendationRound(
            fake_pipeline(),
            fake_research(),
            inputs(mode="discovery", profile=TasteProfile()),
        )

        steps, _ = await collect(round_)

        assert steps[0].step == "selecting_discovery"

    async def test_every_step_carries_a_message(self):
        steps, _ = await collect(RecommendationRound(fake_pipeline(), fake_research(), inputs()))
        assert all(step.message for step in steps)

    async def test_a_rewrite_is_reported(self):
        pipeline = fake_pipeline()
        pipeline.stages.pitches.fact_check.side_effect = [
            PitchValidation(
                valid=False,
                issues=[PitchIssue(claim="a claim", problem="wrong", correction="right")],
            ),
            PitchValidation(valid=True),
        ]

        steps, _ = await collect(RecommendationRound(pipeline, fake_research(), inputs()))

        assert "rewriting" in [step.step for step in steps]
        pipeline.stages.pitches.rewrite.assert_called_once()


class TestSelection:
    async def test_no_albums_is_a_message_for_the_user(self):
        pipeline = fake_pipeline(selected=[])
        round_ = RecommendationRound(pipeline, fake_research(), inputs())

        with pytest.raises(ValueError, match="No matching albums"):
            await collect(round_)

    async def test_discovery_runs_on_an_empty_profile(self):
        """An empty library is a profile with nothing in it, not a missing one."""
        pipeline = fake_pipeline()
        round_ = RecommendationRound(pipeline, fake_research(), inputs(mode="discovery"))

        await collect(round_)

        assert (
            pipeline.stages.selection.select_discovery_albums.call_args.kwargs["profile"].owned
            == []
        )

    async def test_library_mode_passes_the_candidates_through(self):
        pipeline = fake_pipeline()
        given = inputs(already_shown=[AlbumRef(artist="Band0", album="Album0")])

        await collect(RecommendationRound(pipeline, fake_research(), given))

        call = pipeline.stages.selection.select_albums.call_args.kwargs
        assert call["candidates"] == given.candidates
        assert call["already_shown"] == given.already_shown


class TestFamiliarity:
    async def test_not_queried_when_it_was_not_asked_for(self, monkeypatch):
        queried = MagicMock()
        monkeypatch.setattr(round_module.library.AlbumCache, "familiarity", queried)

        await collect(RecommendationRound(fake_pipeline(), fake_research(), inputs()))

        queried.assert_not_called()

    async def test_queried_for_a_preference(self, monkeypatch):
        queried = MagicMock(return_value={})
        monkeypatch.setattr(round_module.library.AlbumCache, "familiarity", queried)

        await collect(
            RecommendationRound(
                fake_pipeline(), fake_research(), inputs(familiarity_pref="comfort")
            )
        )

        queried.assert_called_once()

    async def test_not_queried_in_discovery(self, monkeypatch):
        """Discovery recommends albums the user cannot have played."""
        queried = MagicMock(return_value={})
        monkeypatch.setattr(round_module.library.AlbumCache, "familiarity", queried)

        await collect(
            RecommendationRound(
                fake_pipeline(),
                fake_research(),
                inputs(mode="discovery", profile=TasteProfile(), familiarity_pref="comfort"),
            )
        )

        queried.assert_not_called()

    async def test_a_failed_query_does_not_lose_the_round(self, monkeypatch):
        monkeypatch.setattr(
            round_module.library.AlbumCache,
            "familiarity",
            MagicMock(side_effect=RuntimeError("cache locked")),
        )

        _, result = await collect(
            RecommendationRound(
                fake_pipeline(), fake_research(), inputs(familiarity_pref="comfort")
            )
        )

        assert result is not None


class TestResearch:
    async def test_the_year_is_corrected_from_musicbrainz(self):
        """Plex often carries a reissue's year; MusicBrainz has the original."""
        research = fake_research(
            found=ResearchData(musicbrainz_id="mbid-1", release_date="1999-06-12")
        )

        result = await result_of(RecommendationRound(fake_pipeline(), research, inputs()))

        assert result.recommendations[0].year == 1999

    async def test_an_unparseable_date_leaves_the_year_alone(self):
        research = fake_research(found=ResearchData(musicbrainz_id="mbid-1", release_date="soon"))

        result = await result_of(RecommendationRound(fake_pipeline(), research, inputs()))

        assert result.recommendations[0].year == 2001

    async def test_cover_art_falls_back_to_the_archive(self):
        research = fake_research(
            found=ResearchData(musicbrainz_id="mbid-1", earliest_release_mbid="rel-1"),
            art="https://coverartarchive.org/release/rel-1/front",
        )

        result = await result_of(RecommendationRound(fake_pipeline(), research, inputs()))

        art_url = result.recommendations[0].art_url
        assert art_url is not None
        assert art_url.startswith("/api/external-art?url=")

    async def test_plex_art_is_not_replaced(self):
        pipeline = fake_pipeline(
            selected=[
                AlbumRecommendation(rank="primary", artist="A", album="One", art_url="/api/art/7")
            ]
        )
        research = fake_research(
            found=ResearchData(musicbrainz_id="mbid-1", earliest_release_mbid="rel-1"),
            art="https://coverartarchive.org/release/rel-1/front",
        )

        result = await result_of(RecommendationRound(pipeline, research, inputs()))

        assert result.recommendations[0].art_url == "/api/art/7"

    async def test_a_failed_lookup_warns_but_keeps_the_albums(self):
        research = fake_research()
        research.of_album = AsyncMock(side_effect=RuntimeError("MusicBrainz down"))

        result = await result_of(RecommendationRound(fake_pipeline(), research, inputs()))

        assert len(result.recommendations) == 2
        assert result.research_warning == round_module.NO_RESEARCH

    async def test_no_research_at_all_is_said_plainly(self):
        research = fake_research(found=ResearchData())

        result = await result_of(RecommendationRound(fake_pipeline(), research, inputs()))

        assert result.research_warning == round_module.NO_RESEARCH

    async def test_an_unverifiable_discovery_pick_is_flagged(self):
        research = fake_research(found=ResearchData())

        result = await result_of(
            RecommendationRound(
                fake_pipeline(), research, inputs(mode="discovery", profile=TasteProfile())
            )
        )

        assert result.research_warning is not None

    async def test_a_discovery_pick_that_does_not_fit_is_flagged(self):
        pipeline = fake_pipeline()
        pipeline.stages.facts.matches_request.return_value = False

        result = await result_of(
            RecommendationRound(
                pipeline, fake_research(), inputs(mode="discovery", profile=TasteProfile())
            )
        )

        assert result.research_warning == round_module.FAILED_VALIDATION


class TestGrounding:
    async def test_facts_are_extracted_for_the_primary_only(self):
        pipeline = fake_pipeline()

        await collect(RecommendationRound(pipeline, fake_research(), inputs()))

        pipeline.stages.facts.extract.assert_called_once()
        assert pipeline.stages.facts.extract.call_args.kwargs["ref"].album == "Ágætis byrjun"

    async def test_nothing_is_extracted_without_research(self):
        pipeline = fake_pipeline()
        research = fake_research(found=ResearchData())

        steps, _ = await collect(RecommendationRound(pipeline, research, inputs()))

        pipeline.stages.facts.extract.assert_not_called()
        assert "extracting_facts" not in [step.step for step in steps]

    async def test_a_failed_extraction_still_writes_the_pitch(self):
        pipeline = fake_pipeline()
        pipeline.stages.facts.extract.side_effect = RuntimeError("model refused")

        _, result = await collect(RecommendationRound(pipeline, fake_research(), inputs()))

        pipeline.stages.pitches.write.assert_called_once()
        assert result is not None

    async def test_a_pitch_still_wrong_after_a_rewrite_is_flagged(self):
        pipeline = fake_pipeline()
        pipeline.stages.pitches.fact_check.return_value = PitchValidation(
            valid=False,
            issues=[PitchIssue(claim="a claim", problem="wrong", correction="right")],
        )

        result = await result_of(RecommendationRound(pipeline, fake_research(), inputs()))

        assert result.research_warning == round_module.STILL_UNVERIFIED
        assert pipeline.stages.pitches.rewrite.call_count == 1

    async def test_a_failed_validation_does_not_lose_the_pitch(self):
        pipeline = fake_pipeline()
        pipeline.stages.pitches.fact_check.side_effect = RuntimeError("model refused")

        result = await result_of(RecommendationRound(pipeline, fake_research(), inputs()))

        assert len(result.recommendations) == 2


class TestAbandoned:
    async def test_stops_without_a_result(self):
        """The point is not spending on someone who has closed the tab."""
        pipeline = fake_pipeline()
        round_ = RecommendationRound(
            pipeline, fake_research(), inputs(), AsyncMock(return_value=True)
        )

        _, result = await collect(round_)

        assert result is None
        pipeline.stages.pitches.write.assert_not_called()

    async def test_selection_is_paid_for_before_the_first_check(self):
        """Selection is already in flight; stopping cannot un-spend it."""
        pipeline = fake_pipeline()
        round_ = RecommendationRound(
            pipeline, fake_research(), inputs(), AsyncMock(return_value=True)
        )

        await collect(round_)

        pipeline.stages.selection.select_albums.assert_called_once()

    async def test_a_connected_client_runs_to_the_end(self):
        _, result = await collect(
            RecommendationRound(
                fake_pipeline(), fake_research(), inputs(), AsyncMock(return_value=False)
            )
        )

        assert result is not None


class TestResult:
    async def test_carries_the_session_spend(self):
        """What the round cost is read off the session the stages charged."""
        pipeline = fake_pipeline()
        session_id = pipeline.sessions.create(RecommendSession(prompt="test"))
        pipeline.sessions.add_spend(session_id, 1500, 0.02)

        result = await result_of(
            RecommendationRound(pipeline, fake_research(), inputs(session_id=session_id))
        )

        assert result.token_count == 1500
        assert result.estimated_cost == 0.02

    async def test_returns_what_the_pitches_were_written_onto(self):
        result = await result_of(RecommendationRound(fake_pipeline(), fake_research(), inputs()))

        assert [rec.album for rec in result.recommendations] == ["Ágætis byrjun", "Spiderland"]


def saved(response: RecommendGenerateResponse, **round_inputs) -> Result:
    """Save one response, returning the row the round handed the store."""
    round_ = RecommendationRound(fake_pipeline(), fake_research(), inputs(**round_inputs))
    with patch("backend.recommender.round.results_store") as store:
        round_.save(response)
    return store.save.call_args.args[0]


class TestSave:
    """History is written by the round, as it is for a playlist."""

    def test_is_titled_by_the_primary_pick(self):
        row = saved(RecommendGenerateResponse(recommendations=picks()))

        assert row.title == "Ágætis byrjun by Sigur Rós"
        assert row.artist == "Sigur Rós"

    def test_a_round_without_a_primary_still_has_a_title(self):
        response = RecommendGenerateResponse(
            recommendations=[
                AlbumRecommendation(rank="secondary", artist="Slint", album="Spiderland")
            ]
        )

        row = saved(response)

        assert row.title == "Album Recommendation"
        assert row.artist is None

    def test_the_prompt_and_the_snapshot_are_kept(self):
        response = RecommendGenerateResponse(recommendations=picks(), token_count=42)

        row = saved(response, prompt="something atmospheric")

        assert row.prompt == "something atmospheric"
        assert row.snapshot["token_count"] == 42
        assert row.track_count == 2

    def test_the_hook_becomes_the_subtitle(self):
        primary, secondary = picks()
        primary.pitch = SommelierPitch(hook="Iceland, in slow motion")

        row = saved(RecommendGenerateResponse(recommendations=[primary, secondary]))

        assert row.subtitle == "Iceland, in slow motion"

    def test_an_unpitched_round_falls_back_to_the_prompt(self):
        row = saved(RecommendGenerateResponse(recommendations=picks()), prompt="rainy")

        assert row.subtitle == "rainy"

    def test_art_comes_from_the_primary_first_track(self):
        primary, secondary = picks()
        primary.track_rating_keys = ["101", "102"]

        row = saved(RecommendGenerateResponse(recommendations=[primary, secondary]))

        assert row.art_rating_key == "101"

    def test_a_discovery_pick_has_no_art_key(self):
        row = saved(RecommendGenerateResponse(recommendations=picks()))

        assert row.art_rating_key is None

    def test_the_id_the_store_minted_comes_back(self):
        round_ = RecommendationRound(fake_pipeline(), fake_research(), inputs())
        with patch("backend.recommender.round.results_store") as store:
            store.save.return_value = "an-id"
            assert round_.save(RecommendGenerateResponse(recommendations=picks())) == "an-id"

    def test_a_failed_save_loses_the_history_not_the_albums(self):
        """Nothing here may raise: the user is looking at the result."""
        round_ = RecommendationRound(fake_pipeline(), fake_research(), inputs())
        with patch("backend.recommender.round.results_store") as store:
            store.save.side_effect = RuntimeError("disk full")
            assert round_.save(RecommendGenerateResponse(recommendations=picks())) is None
