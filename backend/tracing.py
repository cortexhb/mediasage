"""Langfuse tracing for the calls that spend a model.

`Tracing` owns the process's Langfuse client. It is built once at startup from
`LangfuseConfig`; the Langfuse SDK caches a client per public key for the life
of the process, so changing the keys means restarting rather than saving.

Nothing here decides what a trace looks like. A pipeline carries `@observe`,
and `LLMClient.complete` attaches the LangChain callback handler that turns
each completion into a generation under that pipeline's span. The handler
reports the model and the provider's token counts on its own, which is why no
call site sets them.

Unconfigured is the ordinary case. The client is then built with
`tracing_enabled=False`, which registers a live no-op: every decorator and
handler still runs and sends nothing. Registering it matters -- with no client
at all, `get_client()` builds a throwaway one on every decorated call.

Top-level rather than under `api/`: `backend.llm` is what reaches for it, and
importing the HTTP layer from a domain package would be a cycle.
"""

import logging
from typing import Any, ClassVar

from langchain_core.callbacks import BaseCallbackHandler
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from backend.config import LangfuseConfig

logger = logging.getLogger(__name__)

# A client registers against a key pair, disabled or not.
DISABLED_KEYS = "disabled"

# Trace attributes LangChain carries in `metadata`, per the Langfuse docs.
SESSION_KEY = "langfuse_session_id"


class Tracing:
    """The process's Langfuse client, and what the LLM client needs from it."""

    _client: ClassVar[Langfuse | None] = None
    _enabled: ClassVar[bool] = False

    @staticmethod
    def configure(config: LangfuseConfig) -> None:
        """Build the client this process traces through.

        Called once, at startup. A second call with different keys cannot take
        effect: the SDK hands back the client it already cached for the first.
        """
        if Tracing._client is not None:
            logger.debug("Langfuse already configured; keys change on restart only")
            return

        if not config.is_configured:
            Tracing._client = Langfuse(
                public_key=DISABLED_KEYS,
                secret_key=DISABLED_KEYS,
                tracing_enabled=False,
            )
            logger.info("Langfuse tracing off: no base URL or keys configured")
            return

        Tracing._client = Langfuse(
            public_key=config.public_key,
            secret_key=config.secret_key.get_secret_value(),
            base_url=config.base_url,
            # None, not "": unset means the SDK's own default.
            environment=config.environment or None,
        )
        Tracing._enabled = True
        logger.info("Langfuse tracing on, sending to %s", config.base_url)

    @staticmethod
    def enabled() -> bool:
        """Whether traces are being sent anywhere."""
        return Tracing._enabled

    @staticmethod
    def callbacks() -> list[BaseCallbackHandler]:
        """The handlers a LangChain call runs under.

        Empty while unconfigured: a disabled handler costs a callback per token
        for nothing, and LangChain is happy with no callbacks at all.
        """
        return [CallbackHandler()] if Tracing._enabled else []

    @staticmethod
    def attributes(session: str) -> dict[str, Any]:
        """Trace attributes for one LangChain call.

        A session groups the several traces one user flow produces -- the
        prompt analysis, the refinement questions and the generation are
        separate requests, and only this ties them together.
        """
        return {SESSION_KEY: session} if session and Tracing._enabled else {}

    @staticmethod
    def record(*, asked: Any = None, answered: Any = None) -> None:
        """Set what the running `@observe` span was asked and what it answered.

        `@observe` captures a function's arguments, which for a method on a
        model is nothing: the request is `self`, and the decorator drops it.
        A streaming run's return value is no better -- it is the generator.
        So both ends are named here instead, at the points they are known.

        Not a span of its own: this updates the one the decorator opened.
        """
        if not Tracing._enabled or Tracing._client is None:
            return
        Tracing._client.update_current_span(input=asked, output=answered)

    @staticmethod
    def shutdown() -> None:
        """Flush what is queued and stop the exporter, on the way out."""
        if Tracing._client is None:
            return
        Tracing._client.shutdown()
        Tracing._client = None
        Tracing._enabled = False
