"""Signing in to Plex from a browser, and finding a server afterwards.

Entry points: `PlexLink.begin`, `PlexLink.claim`, `PlexServers.of`.

Plex's sign-in is a pin exchange, not OAuth 2. `POST /api/v2/pins` hands back
an id and a four-character code, the user approves that code in their own
browser, and `GET /api/v2/pins/{id}` answers with `authToken` once they have.

Both calls are written by hand, for the same reason `backend/llm/ollama.py`
wraps Ollama's admin API by hand: plexapi's `MyPlexPinLogin` starts a thread
and keeps the pin id private, and the SPA polls. Written this way the poll
needs only the pin id and the stored client identifier, so a restart
mid-sign-in loses nothing.

`X-Plex-Client-Identifier` must be stable. plexapi defaults it to the MAC
address, which a recreated container changes -- and a changing identifier
registers a new device on every sign-in, orphaning the previous ones in the
user's account. It is a uuid4, persisted as `plex.client_id`.

Two tokens come out of this, because they are two credentials.
`MyPlexResource.connect()` authenticates with the per-resource `accessToken`,
not the account token: the two coincide for a server the user owns and diverge
for one shared with them. `account_token` lists the servers, `token` talks to
the chosen one.
"""

import logging
import uuid
from typing import Any, Final, Self

import httpx
from plexapi.myplex import MyPlexAccount
from pydantic import BaseModel, ConfigDict, SecretStr

from backend.models import PlexServerChoice
from backend.plex.connection import PlexConnection
from backend.version import Version

logger = logging.getLogger(__name__)

PINS_URL: Final = "https://plex.tv/api/v2/pins"
AUTH_URL: Final = "https://app.plex.tv/auth/#!"

# What the user sees when approving the sign-in.
PRODUCT: Final = "MediaSage"

# Seconds per plex.tv call; none of them is a bulk fetch.
TIMEOUT: Final = 15.0

# `strong=true` asks for the long pin used by the browser flow.
STRONG: Final = {"strong": "true"}


class PlexLinkError(Exception):
    """A plex.tv call failed, or answered something unusable."""


class PlexPin(BaseModel):
    """A pin waiting to be approved in the user's browser."""

    model_config = ConfigDict(frozen=True)

    id: int
    code: str
    # Carries the code, so the user approves this pin.
    url: str
    expires_in: int


class PlexIdentity(BaseModel):
    """Who this installation says it is, on every plex.tv call."""

    model_config = ConfigDict(frozen=True)

    client_id: str

    @staticmethod
    def fresh_client_id() -> str:
        """A new identifier, for an installation that has never signed in."""
        return str(uuid.uuid4())

    @property
    def headers(self) -> dict[str, str]:
        """The `X-Plex-*` headers plex.tv requires."""
        return {
            "accept": "application/json",
            "X-Plex-Product": PRODUCT,
            "X-Plex-Version": Version.current(),
            "X-Plex-Client-Identifier": self.client_id,
            "X-Plex-Device": "MediaSage",
            "X-Plex-Device-Name": PRODUCT,
            "X-Plex-Platform": "Web",
        }


class PlexLink(BaseModel):
    """The browser sign-in, as two stateless calls to plex.tv."""

    model_config = ConfigDict(frozen=True)

    identity: PlexIdentity

    @classmethod
    def of(cls, client_id: str) -> Self:
        """Build for a stored identifier, minting one when there is none yet."""
        return cls(identity=PlexIdentity(client_id=client_id or PlexIdentity.fresh_client_id()))

    async def begin(self, forward_url: str | None = None) -> PlexPin:
        """Create a pin and the address that approves it.

        Args:
            forward_url: Where Plex returns the browser once approved

        Raises:
            PlexLinkError: If plex.tv refused or answered without a code
        """
        answered = await self.ask("POST", PINS_URL, params=STRONG)

        code = answered.get("code")
        pin_id = answered.get("id")
        if not isinstance(code, str) or not isinstance(pin_id, int):
            raise PlexLinkError("Plex did not return a usable pin")

        return PlexPin(
            id=pin_id,
            code=code,
            url=self.approval_url(code, forward_url),
            expires_in=int(answered.get("expiresIn", 0)),
        )

    async def claim(self, pin_id: int) -> SecretStr | None:
        """The account token for an approved pin, or None while it is pending.

        Raises:
            PlexLinkError: If the pin is unknown or has expired
        """
        answered = await self.ask("GET", f"{PINS_URL}/{pin_id}")

        token = answered.get("authToken")
        if isinstance(token, str) and token:
            return SecretStr(token)
        return None

    def approval_url(self, code: str, forward_url: str | None) -> str:
        """Where the user approves `code`, in their own browser."""
        asked = {
            "clientID": self.identity.client_id,
            "code": code,
            "context[device][product]": PRODUCT,
        }
        if forward_url:
            asked["forwardUrl"] = forward_url
        return f"{AUTH_URL}?{httpx.QueryParams(asked)}"

    async def ask(
        self, method: str, url: str, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """One plex.tv call, as the JSON object it answered.

        Raises:
            PlexLinkError: On a refusal, a timeout, or a body that is not an object
        """
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                answered = await client.request(
                    method, url, params=params, headers=self.identity.headers
                )
                answered.raise_for_status()
                body = answered.json()
        except httpx.HTTPStatusError as err:
            raise PlexLinkError(f"Plex refused the request: {err.response.status_code}") from err
        except httpx.HTTPError as err:
            raise PlexLinkError(f"Could not reach plex.tv: {err}") from err
        except ValueError as err:
            raise PlexLinkError("Plex answered with something that is not JSON") from err

        if not isinstance(body, dict):
            raise PlexLinkError("Plex answered with something unexpected")
        return body


class PlexServers(BaseModel):
    """The servers one signed-in account can reach.

    Every call here is synchronous and talks to plex.tv or to a server. Reach
    them from an endpoint through `asyncio.to_thread`.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    account_token: SecretStr
    identity: PlexIdentity
    connect_timeout: float = 30.0

    @property
    def account(self) -> MyPlexAccount:
        """The plex.tv account handle, built per use rather than held.

        Each one costs a `/api/v2/user` round-trip, and the alternative is a
        handle that outlives the token that made it.
        """
        return MyPlexAccount(
            token=self.account_token.get_secret_value(),
            session=None,
            timeout=int(self.connect_timeout),
        )

    def choices(self) -> list[PlexServerChoice]:
        """Every Plex Media Server the account can reach.

        Raises:
            PlexLinkError: If plex.tv would not list them
        """
        try:
            resources = self.account.resources()
        except Exception as err:
            raise PlexLinkError(f"Could not list Plex servers: {err}") from err

        return [
            PlexServerChoice(
                id=resource.clientIdentifier,
                name=resource.name,
                owned=bool(resource.owned),
            )
            for resource in resources
            if "server" in (resource.provides or "")
        ]

    def resolve(self, server_id: str, music_library: str) -> PlexResolution:
        """Find `server_id`, and open the first address that answers.

        Every address is tried through `PlexConnection` rather than plexapi's
        own `connect()`: that one proves the server answers but keeps the URL
        it used private, and it does not prove the music library exists.

        Raises:
            PlexLinkError: If the account cannot see it, or none of its
                addresses answered
        """
        try:
            resource = self.account.resource(server_id)
        except Exception as err:
            raise PlexLinkError(f"That server is not on this account: {err}") from err

        token = SecretStr(resource.accessToken or self.account_token.get_secret_value())
        failure = "Plex listed no address for that server"

        # Ordered local, then remote, then relay, by plexapi's own preference.
        for url in resource.preferred_connections():
            opened = PlexConnection(
                url=url,
                token=token,
                music_library=music_library,
                connect_timeout=self.connect_timeout,
            )
            if opened.is_connected():
                return PlexResolution(
                    url=url, token=token, server_id=server_id, server_name=resource.name
                )
            failure = opened.error or failure
            logger.info("Plex address %s did not answer: %s", url, failure)

        raise PlexLinkError(failure)


class PlexResolution(BaseModel):
    """A server that answered, and how to reach it again."""

    model_config = ConfigDict(frozen=True)

    url: str
    token: SecretStr
    server_id: str
    server_name: str
