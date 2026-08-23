"""One LLM client, bound to the session its costs accrue to.

Every pipeline stage spends tokens on someone's behalf. Wrapping the client
means a stage asks for a completion and gets parsed JSON back, while the cost
line and the session total are recorded without the stage doing either.

Entry points: `MeteredClient`, and `Stage` for anything that spends through one.
"""

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict

from backend.config import config_store
from backend.llm import LLMClient, LLMResponse
from backend.recommender.sessions import SessionStore

logger = logging.getLogger("recommend.cost")

# Stands in for the session id on a call made outside any session.
NO_SESSION = "n/a"


class MeteredClient(BaseModel):
    """An LLM client whose spend lands on one recommendation session."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client: LLMClient
    sessions: SessionStore
    session_id: str = NO_SESSION

    def analyze(self, system: str, prompt: str, label: str, albums: int = 0) -> Any:
        """Spend the analysis model and return the parsed JSON reply."""
        return self._parse(self.client.analyze(prompt, system), label, albums)

    def generate(self, system: str, prompt: str, label: str, albums: int = 0) -> Any:
        """Spend the generation model and return the parsed JSON reply."""
        return self._parse(self.client.generate(prompt, system), label, albums)

    def _parse(self, response: LLMResponse, label: str, albums: int) -> Any:
        """Record what the call cost, then decode what it said."""
        cost = response.cost(config_store.get().llm)
        logger.info(
            "recommend.cost | call=%s model=%s input=%d output=%d cost=%.5f albums=%d session=%s",
            label, response.model, response.input_tokens, response.output_tokens,
            cost, albums, self.session_id,
        )
        self.sessions.add_spend(
            self.session_id, response.input_tokens + response.output_tokens, cost
        )
        return response.parsed()


class Stage(BaseModel):
    """A pipeline stage, bound to the client its calls are charged to.

    Every stage is one or more LLM calls over the same session, so the client
    is held once here rather than passed to each call.
    """

    call: MeteredClient

    @staticmethod
    def as_list(raw: Any) -> list[Any]:
        """Whatever the model returned, as a list.

        Models asked for a JSON array sometimes wrap it in an object or answer
        with a single object. Neither is worth failing a round over.
        """
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            for value in raw.values():
                if isinstance(value, list):
                    return value
            return [raw]
        return []

    @staticmethod
    def as_dict(raw: Any) -> dict[str, Any]:
        """Whatever the model returned, as an object; empty when it is not one."""
        return raw if isinstance(raw, dict) else {}
