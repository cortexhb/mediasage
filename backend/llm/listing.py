"""What models a provider says it serves.

A metadata-only check used to prove settings before they are saved: it shows
the endpoint answers, the credential is accepted, and the configured models
exist -- without spending a completion. Entry point is `ModelListing`.

Every provider is asked through the same SDK LangChain drives it with, built
from the same values `ChatModels.kwargs` builds the chat model from. The probe
therefore reaches whatever the app would reach, and nothing here is a second
copy of where a provider lives.

An index is optional in the OpenAI-compatible protocol: a server can serve
completions and answer 404 to `/models`. That is `supported=False`, saving
unvalidated -- never a refusal, because inference would work.

Timed on `LLMConfig.probe_timeout` with retries off, not `request_timeout`: a
settings form must fail fast, and slow here means the server is down.
"""

import asyncio
import logging
from collections.abc import Iterable
from typing import Final, Self

import anthropic
import httpx
import openai
from google import genai
from google.genai import types as genai_types
from pydantic import BaseModel, ConfigDict

from backend.config import LLMSection, Provider
from backend.llm.constants import PLACEHOLDER_API_KEY
from backend.llm.ollama import OllamaClient

logger = logging.getLogger(__name__)

# Statuses meaning the credential was refused rather than the request.
UNAUTHORISED: Final[frozenset[int]] = frozenset({401, 403})

# Statuses meaning this server serves completions but publishes no index.
NO_INDEX: Final[frozenset[int]] = frozenset({404, 405})

# Gemini returns "models/gemini-2.0-flash" for what the user configures.
GEMINI_PREFIX: Final = "models/"

# Each client's own timeout type; Google's raises httpx's directly.
TIMEOUTS: Final[tuple[type[BaseException], ...]] = (
    httpx.TimeoutException,
    openai.APITimeoutError,
    anthropic.APITimeoutError,
)


class ListingRefused(Exception):
    """A listing that failed with a message already fit for a form."""


class ProviderListing(BaseModel):
    """One provider's SDK, asked which models it serves.

    Subclassed per SDK rather than parameterised: the clients share no base
    class and no error hierarchy, so a table of URLs would only be a second
    guess at what the SDK already knows.
    """

    model_config = ConfigDict(frozen=True)

    def names(self, section: LLMSection) -> tuple[str, ...]:
        """The model names `section`'s provider serves.

        Raises:
            Exception: Whatever the provider's own SDK raises; `ModelListing`
                is the boundary that turns those into an answer
        """
        raise NotImplementedError

    @staticmethod
    def key_of(section: LLMSection) -> str:
        """The credential, or the placeholder a keyless local server demands."""
        return section.api_key.get_secret_value() or PLACEHOLDER_API_KEY


class OpenAIListing(ProviderListing):
    """OpenAI, and any OpenAI-compatible server reached by `endpoint_url`."""

    def names(self, section: LLMSection) -> tuple[str, ...]:
        client = openai.OpenAI(
            api_key=self.key_of(section),
            # None, not "": the SDK's own default is what LangChain uses.
            base_url=section.local_endpoint or None,
            timeout=section.probe_timeout,
            max_retries=0,
        )
        return tuple(model.id for model in client.models.list())


class AnthropicListing(ProviderListing):
    """Anthropic, reached by key at the SDK's own base URL."""

    def names(self, section: LLMSection) -> tuple[str, ...]:
        client = anthropic.Anthropic(
            api_key=self.key_of(section),
            timeout=section.probe_timeout,
            max_retries=0,
        )
        return tuple(model.id for model in client.models.list())


class GeminiListing(ProviderListing):
    """Google's Gemini API, whose names carry a collection prefix."""

    def names(self, section: LLMSection) -> tuple[str, ...]:
        client = genai.Client(
            api_key=self.key_of(section),
            # HttpOptions counts in milliseconds.
            http_options=genai_types.HttpOptions(timeout=int(section.probe_timeout * 1000)),
        )
        return tuple(
            str(model.name or "").removeprefix(GEMINI_PREFIX) for model in client.models.list()
        )


class OllamaListing(ProviderListing):
    """An Ollama server, through the admin client that already owns that call."""

    def names(self, section: LLMSection) -> tuple[str, ...]:
        client = OllamaClient(base_url=section.local_endpoint, timeout=section.probe_timeout)
        listed = client.list_models()
        if listed.error:
            raise ListingRefused(listed.error)
        return tuple(model.name for model in listed.models)


LISTINGS: Final[dict[Provider, ProviderListing]] = {
    "openai": OpenAIListing(),
    "custom": OpenAIListing(),
    "anthropic": AnthropicListing(),
    "gemini": GeminiListing(),
    "ollama": OllamaListing(),
}


class ModelListing(BaseModel):
    """The model names a provider serves, or why none could be listed."""

    model_config = ConfigDict(frozen=True)

    names: tuple[str, ...] = ()
    error: str = ""
    # False when the provider published no index. Distinct from an empty
    # listing, which would otherwise read as "the model does not exist".
    supported: bool = True

    @classmethod
    async def of(cls, section: LLMSection) -> Self:
        """List `section`'s models, spending no tokens and never raising."""
        listing = LISTINGS.get(section.provider)
        if listing is None:
            return cls(supported=False)
        if section.is_local and not section.local_endpoint:
            return cls(supported=False)

        try:
            return cls(names=await asyncio.to_thread(listing.names, section))
        except ListingRefused as err:
            return cls(error=str(err))
        except Exception as err:
            # The boundary the module docstring promises: a settings form has
            # to show every way a provider can refuse.
            logger.debug("Listing %s failed", section.provider, exc_info=err)
            return cls.refusal(err, section.label)

    @classmethod
    def refusal(cls, err: Exception, label: str) -> Self:
        """An SDK failure, as something a settings form can show."""
        status = cls.status_of(err)
        if status in UNAUTHORISED:
            return cls(error="Invalid API key")
        if status in NO_INDEX:
            return cls(supported=False)
        if status is not None:
            return cls(error=f"{label} refused the request: HTTP {status}")
        if cls.timed_out(err):
            return cls(error=f"Timed out connecting to {label}")
        return cls(error=f"Cannot connect to {label}")

    @staticmethod
    def status_of(err: Exception) -> int | None:
        """The HTTP status an SDK error carries, whichever SDK raised it.

        `status_code` on the OpenAI and Anthropic clients, `code` on Google's.
        None means the request never got a reply.
        """
        for attribute in ("status_code", "code"):
            value = getattr(err, attribute, None)
            if isinstance(value, int):
                return value
        return None

    @staticmethod
    def timed_out(err: BaseException) -> bool:
        """Whether a failure was a timeout, whichever SDK wrapped it.

        The cause chain is walked as well as the exception: the clients raise
        their own type `from` httpx's, and only one of the two is declared here.
        """
        cause: BaseException | None = err
        while cause is not None:
            if isinstance(cause, TIMEOUTS):
                return True
            cause = cause.__cause__
        return False

    def missing(self, wanted: Iterable[str]) -> tuple[str, ...]:
        """Which of `wanted` this provider did not list.

        Empty whenever the listing is unusable -- unsupported, failed, or empty
        -- so a provider that will not enumerate never rejects a save.

        Matching is case-insensitive and ignores an Ollama-style `:tag`: a
        server lists `llama3:latest` for what the user typed as `llama3`, and an
        exact comparison would refuse a model that is really there.
        """
        if not self.supported or self.error or not self.names:
            return ()
        served = {self.loosely(name) for name in self.names}
        return tuple(name for name in wanted if self.loosely(name) not in served)

    @staticmethod
    def loosely(name: str) -> str:
        """A model name reduced to what two spellings of it have in common."""
        return name.split(":", 1)[0].strip().casefold()
