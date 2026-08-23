"""Whether settings that have not been saved yet actually work.

A probe is built against a candidate configuration: it connects to Plex, or
spends one real completion, and reports what happened without raising. Both
the wizard and the settings page run one before writing, so a wrong credential
is a form error rather than something the user discovers on their next
generation.

Nothing here writes or publishes anything -- a probe answers, the caller
decides whether to commit.
"""

import asyncio
from typing import Final, Self

from pydantic import BaseModel, ConfigDict

from backend.config import ConfigUpdate, LLMSection, MediasageConfig, PlexConfig
from backend.llm import LLMClient
from backend.plex import PlexClient

# Two words: every probe is billed, and every provider can manage it.
PROBE_PROMPT: Final = "hi"
PROBE_SYSTEM: Final = "Reply with one word."


class Probe(BaseModel):
    """The outcome of trying one dependency: an empty error means it answered."""

    model_config = ConfigDict(frozen=True)

    error: str = ""

    @property
    def ok(self) -> bool:
        """Whether the dependency answered."""
        return not self.error

    @classmethod
    async def rejection(cls, update: ConfigUpdate, config: MediasageConfig) -> str:
        """Why `config` must not be saved, or empty when nothing objects.

        Only what the change could break is probed: editing a price must not
        spend a completion, nor fail because the provider happens to be down.
        """
        if update.reconnects("plex"):
            plex = await PlexProbe.of(config.plex)
            if not plex.ok:
                return f"Plex: {plex.error}"

        if update.reconnects("llm"):
            llm = await LLMProbe.of(config.llm)
            if not llm.ok:
                return f"{config.llm.label}: {llm.error}"

        return ""


class PlexProbe(Probe):
    """What a Plex server said when asked to connect."""

    server_name: str | None = None
    # Read off the probe's own client rather than the held one: the wizard
    # shows these next, and a save replaces what the process holds.
    music_libraries: list[str] = []

    @classmethod
    async def of(cls, config: PlexConfig) -> Self:
        """Connect to `config` and report the outcome.

        Never raises: a bad URL, a bad token and an unreachable host are all
        answers a form has to show rather than failures of this call.
        """
        try:
            client = await asyncio.to_thread(PlexClient.of, config)
        except Exception as err:
            return cls(error=str(err))

        if not client.connection.is_connected():
            return cls(error=client.connection.error or "Connection failed")

        return cls(
            server_name=client.connection.server_name,
            music_libraries=client.connection.music_libraries(),
        )


class LLMProbe(Probe):
    """What a provider said when asked for one completion.

    A real call rather than a reachability check: a key can be valid and the
    model name wrong, and only the provider knows which.
    """

    @classmethod
    async def of(cls, section: LLMSection) -> Self:
        """Spend one completion against `section` and report the outcome."""
        try:
            await asyncio.to_thread(
                LLMClient.of(section).complete, PROBE_PROMPT, PROBE_SYSTEM, "analysis"
            )
        except Exception as err:
            return cls(error=cls.friendly(str(err), section.label))
        return cls()

    @staticmethod
    def friendly(message: str, provider_name: str) -> str:
        """A provider SDK error, as something a settings form can show."""
        if any(token in message for token in ("401", "Unauthorized", "AuthenticationError")):
            return "Invalid API key"
        if "Could not resolve" in message or "connection" in message.lower():
            return f"Cannot connect to {provider_name}"
        return message

