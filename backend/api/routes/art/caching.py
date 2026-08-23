"""How long a browser may keep one proxied image.

Shared by both proxies: Plex art is immutable because Plex mints a new thumb
path per artwork, external art is not.
"""

from pydantic import BaseModel, ConfigDict


class CachePolicy(BaseModel):
    """How long a browser may keep one proxied image."""

    model_config = ConfigDict(frozen=True)

    max_age: int
    immutable: bool = False

    @property
    def header(self) -> str:
        """The `Cache-Control` value this policy asks the browser for."""
        suffix = ", immutable" if self.immutable else ""
        return f"public, max-age={self.max_age}{suffix}"
