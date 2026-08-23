"""The failure every provider call can raise.

Lives on its own because both halves of the client raise it: `chat` when no
model is configured for a role, `client` when the provider answers with
nothing. `LLMNotConfigured` narrows it to the one case a caller can act on --
no provider was ever set up. `JSONParseError` stays in `json_parse`, which is
the only thing that raises it.
"""


class LLMError(RuntimeError):
    """Raised when a provider returns nothing usable."""


class LLMNotConfigured(LLMError):
    """Raised when work needs a provider and none has been configured."""
