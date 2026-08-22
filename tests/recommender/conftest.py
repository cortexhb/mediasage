"""Fixtures for the recommender package: a scripted LLM and a metered client.

Every stage takes a `MeteredClient`, so a test scripts what the model replies
and then reads back the prompts it was sent. `LLMClient` is validated by type
on both models, so the stand-in has to be specced against it.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.config import MediasageConfig
from backend.config.store import config_store
from backend.library import AlbumCandidate
from backend.llm import LLMClient, LLMResponse
from backend.recommender.calls import MeteredClient
from backend.recommender.sessions import SessionStore


def reply(role: str = "analysis") -> LLMResponse:
    """A completion with token counts, so cost logging has something to read."""
    return LLMResponse(
        content="{}", input_tokens=100, output_tokens=50, model="test-model", role=role
    )


def scripted_llm(*replies: Any) -> MagicMock:
    """An LLM client that decodes to `replies` in order, one per call.

    The stage under test never sees the raw completion -- `MeteredClient` hands
    it whatever `parse_json_response` returns -- so the reply is scripted there.
    """
    client = MagicMock(spec=LLMClient)
    client.analyze.return_value = reply("analysis")
    client.generate.return_value = reply("generation")
    client.parse_json_response.side_effect = list(replies) or [{}]
    return client


def prompts_of(method: MagicMock) -> tuple[str, str]:
    """The (system, user) prompts of the last call to `analyze` or `generate`.

    `LLMClient` takes them the other way round; naming them here keeps a test
    from asserting against the wrong one.
    """
    user, system = method.call_args[0]
    return system, user


def candidate(artist: str, album: str, **overrides: Any) -> AlbumCandidate:
    """A library album, keyed on its own name unless told otherwise."""
    fields: dict[str, Any] = {
        "parent_rating_key": overrides.pop("parent_rating_key", f"{artist}:{album}"),
        "album": album,
        "album_artist": artist,
        "year": 1999,
        "genres": ["Rock"],
        "track_rating_keys": ["1", "2"],
        "track_count": 2,
    }
    fields.update(overrides)
    return AlbumCandidate(**fields)


@pytest.fixture(autouse=True)
def llm_config(monkeypatch):
    """Install a real config: every metered call prices itself off it.

    Prices are set, so a test can tell a charged call from an uncharged one; an
    unpriced config reports no cost, which would make both look the same.
    """
    config = MediasageConfig(llm={
        "provider": "anthropic",
        "context_window": 200000,
        "cost_analysis_input": 3.0,
        "cost_analysis_output": 15.0,
        "cost_generation_input": 1.0,
        "cost_generation_output": 5.0,
    })
    monkeypatch.setattr(config_store, "config", config)
    return config


@pytest.fixture
def limits(llm_config):
    """The installed recommendation tunables, so a test asserts against them."""
    return llm_config.recommend


@pytest.fixture
def sessions() -> SessionStore:
    return SessionStore()


@pytest.fixture
def metered(sessions):
    """Build a metered client over a scripted LLM, returning both."""

    def build(*replies: Any) -> tuple[MeteredClient, MagicMock]:
        client = scripted_llm(*replies)
        return MeteredClient(client=client, sessions=sessions), client

    return build
