"""Tests for one generation round: what it reports, and what it survives."""

from unittest.mock import AsyncMock, MagicMock

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
    TasteProfile,
)
from backend.recommender.round import RecommendationRound, RoundInputs, Step
from backend.recommender.sessions import SessionStore
from tests.recommender.conftest import candidate


def picks() -> list[AlbumRecommendation]:
    """One primary and one secondary, as selection returns them."""
    return [
        AlbumRecommendation(rank="primary", artist="Sigur Rós", album="Ágætis byrjun", year=2001),
        AlbumRecommendation(rank="secondary", artist="Slint", album="Spiderland"),
    ]


def fake_pipeline(**overrides) -> MagicMock:
    """A pipeline whose stages answer instantly, with a real session store."""
    pipeline = MagicMock()
    pipeline.sessions = SessionStore()
    pipeline.select_albums.return_value = overrides.pop("selected", picks())
    pipeline.select_discovery_albums.return_value = overrides.pop("discovered", picks())
    pipeline.extract_facts.return_value = ExtractedFacts(origin_story="Recorded in Reykjavik")
    pipeline.validate_discovery_album.return_value = True
    pipeline.validate_pitch.return_value = PitchValidation(valid=True)
    pipeline.write_pitches.side_effect = lambda **kwargs: kwargs["recommendations"]
    for name, value in overrides.items():
        getattr(pipeline, name).return_value = value
    return pipeline


def fake_research(**overrides) -> MagicMock:
    """A research client that finds one album by default."""
    client = MagicMock()
    client.of_album = AsyncMock(
        return_value=overrides.pop("found", ResearchData(musicbrainz_id="mbid-1"))
    )
    client.cover_art = AsyncMock(return_value=overrides.pop("art", None))
    return client


def inputs(**overrides) -> RoundInputs:
    fields = {
        "session_id": "rec_test",
        "prompt": "something atmospheric",
        "candidates": [candidate(f"Band{i}", f"Album{i}") for i in range(5)],
    }
    fields.update(overrides)
    return RoundInputs(**fields)


async def collect(round_: RecommendationRound) -> tuple[list[Step], RecommendGenerateResponse | None]:
    """Drain a round into its steps and its result."""
    steps: list[Step] = []
    result = None
    async for update in round_.run():
        if isinstance(update, Step):
            steps.append(update)
        else:
            result = update
    return steps, result


class TestProgress:
    async def test_reports_every_stage_in_order(self):
        pipeline = fake_pipeline()
        round_ = RecommendationRound(pipeline, fake_research(), inputs())

        steps, result = await collect(round_)

        assert [step.step for step in steps] == [
            "selecting_library", "researching_primary", "researching_secondary",
            "extracting_facts", "writing", "validating",
        ]
        assert result is not None

    async def test_discovery_says_it_is_discovering(self):
        round_ = RecommendationRound(
            fake_pipeline(), fake_research(),
            inputs(mode="discovery", profile=TasteProfile()),
        )

        steps, _ = await collect(round_)

        assert steps[0].step == "selecting_discovery"

    async def test_every_step_carries_a_message(self):
        steps, _ = await collect(
            RecommendationRound(fake_pipeline(), fake_research(), inputs())
        )
        assert all(step.message for step in steps)

    async def test_a_rewrite_is_reported(self):
        pipeline = fake_pipeline()
        pipeline.validate_pitch.side_effect = [
            PitchValidation(valid=False, issues=[
                PitchIssue(claim="a claim", problem="wrong", correction="right")
            ]),
            PitchValidation(valid=True),
        ]

        steps, _ = await collect(
            RecommendationRound(pipeline, fake_research(), inputs())
        )

        assert "rewriting" in [step.step for step in steps]
        pipeline.rewrite_pitch.assert_called_once()


class TestSelection:
    async def test_no_albums_is_a_message_for_the_user(self):
        pipeline = fake_pipeline(selected=[])
        round_ = RecommendationRound(pipeline, fake_research(), inputs())

        with pytest.raises(ValueError, match="No matching albums"):
            await collect(round_)

    async def test_discovery_without_a_profile_is_refused(self):
        """Recommending outside the library needs to know what is in it."""
        round_ = RecommendationRound(
            fake_pipeline(), fake_research(), inputs(mode="discovery")
        )

        with pytest.raises(ValueError, match="requires a library profile"):
            await collect(round_)

    async def test_library_mode_passes_the_candidates_through(self):
        pipeline = fake_pipeline()
        given = inputs(already_shown=[AlbumRef(artist="Band0", album="Album0")])

        await collect(RecommendationRound(pipeline, fake_research(), given))

        call = pipeline.select_albums.call_args.kwargs
        assert call["candidates"] == given.candidates
        assert call["already_shown"] == given.already_shown


class TestFamiliarity:
    async def test_not_queried_when_it_was_not_asked_for(self, monkeypatch):
        queried = MagicMock()
        monkeypatch.setattr(round_module.library.albums, "familiarity", queried)

        await collect(RecommendationRound(fake_pipeline(), fake_research(), inputs()))

        queried.assert_not_called()

    async def test_queried_for_a_preference(self, monkeypatch):
        queried = MagicMock(return_value={})
        monkeypatch.setattr(round_module.library.albums, "familiarity", queried)

        await collect(RecommendationRound(
            fake_pipeline(), fake_research(), inputs(familiarity_pref="comfort")
        ))

        queried.assert_called_once()

    async def test_not_queried_in_discovery(self, monkeypatch):
        """Discovery recommends albums the user cannot have played."""
        queried = MagicMock(return_value={})
        monkeypatch.setattr(round_module.library.albums, "familiarity", queried)

        await collect(RecommendationRound(
            fake_pipeline(), fake_research(),
            inputs(mode="discovery", profile=TasteProfile(), familiarity_pref="comfort"),
        ))

        queried.assert_not_called()

    async def test_a_failed_query_does_not_lose_the_round(self, monkeypatch):
        monkeypatch.setattr(
            round_module.library.albums, "familiarity",
            MagicMock(side_effect=RuntimeError("cache locked")),
        )

        _, result = await collect(RecommendationRound(
            fake_pipeline(), fake_research(), inputs(familiarity_pref="comfort")
        ))

        assert result is not None


class TestResearch:
    async def test_the_year_is_corrected_from_musicbrainz(self):
        """Plex often carries a reissue's year; MusicBrainz has the original."""
        research = fake_research(
            found=ResearchData(musicbrainz_id="mbid-1", release_date="1999-06-12")
        )

        _, result = await collect(
            RecommendationRound(fake_pipeline(), research, inputs())
        )

        assert result.recommendations[0].year == 1999

    async def test_an_unparseable_date_leaves_the_year_alone(self):
        research = fake_research(
            found=ResearchData(musicbrainz_id="mbid-1", release_date="soon")
        )

        _, result = await collect(
            RecommendationRound(fake_pipeline(), research, inputs())
        )

        assert result.recommendations[0].year == 2001

    async def test_cover_art_falls_back_to_the_archive(self):
        research = fake_research(
            found=ResearchData(musicbrainz_id="mbid-1", earliest_release_mbid="rel-1"),
            art="https://coverartarchive.org/release/rel-1/front",
        )

        _, result = await collect(
            RecommendationRound(fake_pipeline(), research, inputs())
        )

        assert result.recommendations[0].art_url.startswith("/api/external-art?url=")

    async def test_plex_art_is_not_replaced(self):
        pipeline = fake_pipeline(selected=[
            AlbumRecommendation(rank="primary", artist="A", album="One", art_url="/api/art/7")
        ])
        research = fake_research(
            found=ResearchData(musicbrainz_id="mbid-1", earliest_release_mbid="rel-1"),
            art="https://coverartarchive.org/release/rel-1/front",
        )

        _, result = await collect(RecommendationRound(pipeline, research, inputs()))

        assert result.recommendations[0].art_url == "/api/art/7"

    async def test_a_failed_lookup_warns_but_keeps_the_albums(self):
        research = fake_research()
        research.of_album = AsyncMock(side_effect=RuntimeError("MusicBrainz down"))

        _, result = await collect(
            RecommendationRound(fake_pipeline(), research, inputs())
        )

        assert len(result.recommendations) == 2
        assert result.research_warning == round_module.NO_RESEARCH

    async def test_no_research_at_all_is_said_plainly(self):
        research = fake_research(found=ResearchData())

        _, result = await collect(
            RecommendationRound(fake_pipeline(), research, inputs())
        )

        assert result.research_warning == round_module.NO_RESEARCH

    async def test_an_unverifiable_discovery_pick_is_flagged(self):
        research = fake_research(found=ResearchData())

        _, result = await collect(RecommendationRound(
            fake_pipeline(), research, inputs(mode="discovery", profile=TasteProfile())
        ))

        assert result.research_warning is not None

    async def test_a_discovery_pick_that_does_not_fit_is_flagged(self):
        pipeline = fake_pipeline()
        pipeline.validate_discovery_album.return_value = False

        _, result = await collect(RecommendationRound(
            pipeline, fake_research(), inputs(mode="discovery", profile=TasteProfile())
        ))

        assert result.research_warning == round_module.FAILED_VALIDATION


class TestGrounding:
    async def test_facts_are_extracted_for_the_primary_only(self):
        pipeline = fake_pipeline()

        await collect(RecommendationRound(pipeline, fake_research(), inputs()))

        pipeline.extract_facts.assert_called_once()
        assert pipeline.extract_facts.call_args.kwargs["ref"].album == "Ágætis byrjun"

    async def test_nothing_is_extracted_without_research(self):
        pipeline = fake_pipeline()
        research = fake_research(found=ResearchData())

        steps, _ = await collect(RecommendationRound(pipeline, research, inputs()))

        pipeline.extract_facts.assert_not_called()
        assert "extracting_facts" not in [step.step for step in steps]

    async def test_a_failed_extraction_still_writes_the_pitch(self):
        pipeline = fake_pipeline()
        pipeline.extract_facts.side_effect = RuntimeError("model refused")

        _, result = await collect(
            RecommendationRound(pipeline, fake_research(), inputs())
        )

        pipeline.write_pitches.assert_called_once()
        assert result is not None

    async def test_a_pitch_still_wrong_after_a_rewrite_is_flagged(self):
        pipeline = fake_pipeline()
        pipeline.validate_pitch.return_value = PitchValidation(
            valid=False,
            issues=[PitchIssue(claim="a claim", problem="wrong", correction="right")],
        )

        _, result = await collect(
            RecommendationRound(pipeline, fake_research(), inputs())
        )

        assert result.research_warning == round_module.STILL_UNVERIFIED
        assert pipeline.rewrite_pitch.call_count == 1

    async def test_a_failed_validation_does_not_lose_the_pitch(self):
        pipeline = fake_pipeline()
        pipeline.validate_pitch.side_effect = RuntimeError("model refused")

        _, result = await collect(
            RecommendationRound(pipeline, fake_research(), inputs())
        )

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
        pipeline.write_pitches.assert_not_called()

    async def test_selection_is_paid_for_before_the_first_check(self):
        """Selection is already in flight; stopping cannot un-spend it."""
        pipeline = fake_pipeline()
        round_ = RecommendationRound(
            pipeline, fake_research(), inputs(), AsyncMock(return_value=True)
        )

        await collect(round_)

        pipeline.select_albums.assert_called_once()

    async def test_a_connected_client_runs_to_the_end(self):
        _, result = await collect(RecommendationRound(
            fake_pipeline(), fake_research(), inputs(), AsyncMock(return_value=False)
        ))

        assert result is not None


class TestResult:
    async def test_carries_the_session_spend(self):
        """What the round cost is read off the session the stages charged."""
        pipeline = fake_pipeline()
        session_id = pipeline.sessions.create(RecommendSession(prompt="test"))
        pipeline.sessions.add_spend(session_id, 1500, 0.02)

        _, result = await collect(RecommendationRound(
            pipeline, fake_research(), inputs(session_id=session_id)
        ))

        assert result.token_count == 1500
        assert result.estimated_cost == 0.02

    async def test_returns_what_the_pitches_were_written_onto(self):
        _, result = await collect(
            RecommendationRound(fake_pipeline(), fake_research(), inputs())
        )

        assert [rec.album for rec in result.recommendations] == [
            "Ágætis byrjun", "Spiderland"
        ]
