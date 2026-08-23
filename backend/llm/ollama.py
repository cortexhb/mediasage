"""Ollama's administrative API.

Model discovery and liveness for an Ollama server, used by the settings UI and
the setup wizard. Entry point is `OllamaClient`.

These are not completions — LangChain's `ChatOllama` handles those. This covers
`/api/tags` and `/api/show`, which LangChain does not expose, via the official
`ollama` SDK rather than hand-rolled HTTP.

Methods return a response model carrying `error` rather than raising: the caller
is a settings page probing a server the user may have typed wrong, where "cannot
reach it" is an expected answer, not a fault.
"""

import logging
from typing import Any, Self

import httpx
import ollama
from pydantic import BaseModel, ConfigDict

from backend.config import config_store
from backend.llm.constants import CONTEXT_LENGTH_SUFFIX, NUM_CTX_PARAMETER
from backend.llm.models import (
    OllamaModel,
    OllamaModelInfo,
    OllamaModelsResponse,
    OllamaStatus,
)

logger = logging.getLogger(__name__)


class OllamaClient(BaseModel):
    """One Ollama server, addressed for administration rather than inference."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    base_url: str
    timeout: float

    @classmethod
    def configured(cls, base_url: str = "") -> Self:
        """A client for `base_url`, or for whatever endpoint is configured.

        The settings form probes a URL before it is saved, so the typed one
        wins over the stored one.
        """
        llm = config_store.get().llm
        return cls(base_url=base_url or llm.local_endpoint, timeout=llm.probe_timeout)

    @property
    def api(self) -> ollama.Client:
        """The SDK client, rebuilt per call so no socket outlives the request."""
        return ollama.Client(host=self.base_url, timeout=self.timeout)

    def list_models(self) -> OllamaModelsResponse:
        """List the models this server has pulled.

        Returns:
            The models, or a response carrying the reason none could be listed
        """
        try:
            listing = self.api.list()
        except httpx.ConnectError:
            return OllamaModelsResponse(error=f"Cannot reach Ollama at {self.base_url}")
        except httpx.TimeoutException:
            return OllamaModelsResponse(
                error=f"Timeout connecting to Ollama at {self.base_url}"
            )
        except (ollama.RequestError, ollama.ResponseError, httpx.HTTPError) as err:
            logger.exception("Error listing Ollama models")
            return OllamaModelsResponse(error=str(err))

        models = [
            OllamaModel(
                name=entry.model or "",
                size=entry.size or 0,
                modified_at=str(entry.modified_at or ""),
            )
            for entry in listing.models
        ]
        return OllamaModelsResponse(models=models)

    def model_info(self, model_name: str) -> OllamaModelInfo | None:
        """Describe one pulled model, including its context window.

        Args:
            model_name: Name of the model, e.g. "llama3:8b"

        Returns:
            The model's details, or None if it is unknown or unreachable
        """
        try:
            shown = self.api.show(model_name)
        except ollama.ResponseError as err:
            if err.status_code != 404:
                logger.exception("Error getting Ollama model info")
            return None
        except (ollama.RequestError, httpx.HTTPError):
            logger.exception("Error getting Ollama model info")
            return None

        return OllamaModelInfo(
            name=model_name,
            context_window=self.context_window_of(shown),
            parameter_size=(shown.details.parameter_size if shown.details else None),
        )

    @staticmethod
    def context_window_of(shown: Any) -> int | None:
        """Read a model's context window out of an `/api/show` response.

        A `num_ctx` parameter wins over the architecture's native length: the
        user set it deliberately and it is what the server will allocate. None
        when neither is present, so the caller asks rather than guesses.
        """
        native = next(
            (
                value
                for key, value in (shown.modelinfo or {}).items()
                if key.endswith(CONTEXT_LENGTH_SUFFIX) and isinstance(value, int)
            ),
            None,
        )

        declared = None
        for line in (shown.parameters or "").lower().splitlines():
            parts = line.split()
            if NUM_CTX_PARAMETER not in parts:
                continue
            index = parts.index(NUM_CTX_PARAMETER)
            if index + 1 < len(parts) and parts[index + 1].isdigit():
                declared = int(parts[index + 1])

        return declared if declared is not None else native

    def status(self) -> OllamaStatus:
        """Report whether this server is reachable and has models.

        Returns:
            Connection state, model count, and the reason for any failure
        """
        listing = self.list_models()

        if listing.error:
            return OllamaStatus(connected=False, model_count=0, error=listing.error)

        if not listing.models:
            return OllamaStatus(
                connected=True,
                model_count=0,
                error="Connected but no models installed. Run `ollama pull llama3`",
            )

        return OllamaStatus(connected=True, model_count=len(listing.models))
