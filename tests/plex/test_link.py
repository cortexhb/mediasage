"""Tests for the browser sign-in and the server list it unlocks.

plex.tv is answered by a `MockTransport`, so the real request is built,
serialised and parsed -- the headers and query string under test are the ones
that would go over the wire.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

import httpx
import pytest
from pydantic import SecretStr

from backend.plex.link import (
    PINS_URL,
    PlexIdentity,
    PlexLink,
    PlexLinkError,
    PlexServers,
)

CLIENT_ID = "fixed-client-id"


def scripted(*answers: httpx.Response | Exception):
    """Patch `httpx.AsyncClient` so every call pops the next scripted answer.

    Returns the patcher and the list the requests are recorded into.
    """
    remaining = list(answers)
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if not remaining:
            raise AssertionError(f"No scripted answer left for {request.url}")
        answer = remaining.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    # Captured first: the patch replaces the attribute this would look up.
    real = httpx.AsyncClient

    def build(**_kwargs) -> httpx.AsyncClient:
        return real(transport=httpx.MockTransport(handle))

    return patch("backend.plex.link.httpx.AsyncClient", build), seen


def answered(payload, status: int = 200) -> httpx.Response:
    """One plex.tv answer, as the real response type."""
    return httpx.Response(status, json=payload)


def link() -> PlexLink:
    """A sign-in helper on a fixed identifier, so headers are assertable."""
    return PlexLink.of(CLIENT_ID)


def resource(
    name: str = "Living Room",
    *,
    identifier: str = "abc123",
    owned: bool = True,
    provides: str | None = "server",
    access_token: str | None = "resource-token",
    connections: tuple[str, ...] = ("http://local:32400",),
) -> SimpleNamespace:
    """A stand-in for a plexapi resource, carrying only what is read."""
    return SimpleNamespace(
        name=name,
        clientIdentifier=identifier,
        owned=owned,
        provides=provides,
        accessToken=access_token,
        preferred_connections=lambda: list(connections),
    )


def servers() -> PlexServers:
    """A signed-in server list; its `account` is patched per test."""
    return PlexServers(
        account_token=SecretStr("account-token"),
        identity=PlexIdentity(client_id=CLIENT_ID),
    )


def connecting(*urls: str) -> MagicMock:
    """A `PlexConnection` stand-in that answers only on `urls`."""

    def build(url: str, **_kwargs) -> MagicMock:
        opened = MagicMock()
        opened.is_connected.return_value = url in urls
        opened.error = None if url in urls else f"{url} refused"
        return opened

    return MagicMock(side_effect=build)


class TestIdentity:
    def test_a_fresh_identifier_is_unique(self):
        """Reused across installations it would collide in the user's account."""
        assert PlexIdentity.fresh_client_id() != PlexIdentity.fresh_client_id()

    def test_the_stored_identifier_is_kept(self):
        """A new one on every sign-in orphans the device already registered."""
        assert PlexLink.of(CLIENT_ID).identity.client_id == CLIENT_ID

    def test_one_is_minted_when_there_is_none(self):
        assert PlexLink.of("").identity.client_id != ""

    def test_the_headers_name_this_installation(self):
        headers = PlexIdentity(client_id=CLIENT_ID).headers

        assert headers["X-Plex-Client-Identifier"] == CLIENT_ID
        assert headers["X-Plex-Product"] == "MediaSage"


class TestBegin:
    async def test_a_pin_is_returned_with_its_approval_url(self):
        patcher, seen = scripted(answered({"id": 42, "code": "WXYZ", "expiresIn": 900}))
        with patcher:
            pin = await link().begin()

        assert (pin.id, pin.code, pin.expires_in) == (42, "WXYZ", 900)
        assert "code=WXYZ" in pin.url
        assert f"clientID={CLIENT_ID}" in pin.url
        assert str(seen[0].url).startswith(PINS_URL)

    async def test_a_strong_pin_is_asked_for(self):
        """The short pin is for a TV remote; the browser flow needs the long one."""
        patcher, seen = scripted(answered({"id": 1, "code": "WXYZ"}))
        with patcher:
            await link().begin()

        assert seen[0].url.params["strong"] == "true"

    async def test_the_identity_headers_are_sent(self):
        patcher, seen = scripted(answered({"id": 1, "code": "WXYZ"}))
        with patcher:
            await link().begin()

        assert seen[0].headers["x-plex-client-identifier"] == CLIENT_ID

    async def test_a_forward_url_is_carried(self):
        """Without it Plex leaves the user on its own page after approving."""
        patcher, _ = scripted(answered({"id": 1, "code": "WXYZ"}))
        with patcher:
            pin = await link().begin("http://mediasage.local/settings")

        assert "forwardUrl=http" in pin.url

    @pytest.mark.parametrize("body", [{"id": 1}, {"code": "WXYZ"}, {"id": "1", "code": "WXYZ"}])
    async def test_a_pin_without_both_halves_is_refused(self, body):
        """The poll needs the id and the user needs the code; neither is guessable."""
        patcher, _ = scripted(answered(body))
        with patcher, pytest.raises(PlexLinkError, match="usable pin"):
            await link().begin()

    async def test_a_missing_expiry_is_zero_rather_than_a_failure(self):
        """It is only what the UI counts down; the pin still works without it."""
        patcher, _ = scripted(answered({"id": 1, "code": "WXYZ"}))
        with patcher:
            pin = await link().begin()

        assert pin.expires_in == 0


class TestClaim:
    async def test_an_approved_pin_hands_back_the_token(self):
        patcher, seen = scripted(answered({"id": 42, "authToken": "plex-token"}))
        with patcher:
            token = await link().claim(42)

        assert token is not None
        assert token.get_secret_value() == "plex-token"
        assert str(seen[0].url) == f"{PINS_URL}/42"

    @pytest.mark.parametrize("body", [{"id": 42}, {"id": 42, "authToken": None}, {"authToken": ""}])
    async def test_an_unapproved_pin_is_pending_rather_than_an_error(self, body):
        """The SPA polls this; every unapproved answer must be the same one."""
        patcher, _ = scripted(answered(body))
        with patcher:
            assert await link().claim(42) is None


class TestAsk:
    async def test_a_refusal_carries_the_status(self):
        patcher, _ = scripted(answered({"error": "gone"}, status=404))
        with patcher, pytest.raises(PlexLinkError, match="404"):
            await link().claim(42)

    async def test_an_unreachable_host_is_reported(self):
        patcher, _ = scripted(httpx.ConnectError("no route"))
        with patcher, pytest.raises(PlexLinkError, match=r"Could not reach plex\.tv"):
            await link().begin()

    async def test_a_body_that_is_not_json_is_reported(self):
        patcher, _ = scripted(httpx.Response(200, text="<html>maintenance</html>"))
        with patcher, pytest.raises(PlexLinkError, match="not JSON"):
            await link().begin()

    async def test_a_body_that_is_not_an_object_is_reported(self):
        patcher, _ = scripted(answered([1, 2, 3]))
        with patcher, pytest.raises(PlexLinkError, match="unexpected"):
            await link().begin()


class TestChoices:
    def account(self, *resources, **overrides) -> MagicMock:
        """A `MyPlexAccount` stand-in listing `resources`."""
        stand_in = MagicMock()
        stand_in.resources.return_value = list(resources)
        stand_in.configure_mock(**overrides)
        return stand_in

    def listed(self, account) -> list:
        with patch.object(PlexServers, "account", new_callable=PropertyMock, return_value=account):
            return servers().choices()

    def test_every_server_is_offered(self):
        choices = self.listed(
            self.account(resource("Living Room"), resource("Attic", identifier="def456"))
        )

        assert [(one.id, one.name) for one in choices] == [
            ("abc123", "Living Room"),
            ("def456", "Attic"),
        ]

    def test_a_shared_server_is_offered_too(self):
        """Not owning it does not stop it answering; the picker says which is which."""
        choices = self.listed(self.account(resource(owned=False)))

        assert choices[0].owned is False

    @pytest.mark.parametrize("provides", ["player", "controller,player", ""])
    def test_what_is_not_a_server_is_dropped(self, provides):
        """A phone running Plex is a resource on the account and cannot be synced."""
        assert self.listed(self.account(resource(provides=provides))) == []

    def test_a_resource_that_provides_nothing_is_dropped(self):
        """plexapi leaves `provides` as None rather than an empty string."""
        assert self.listed(self.account(resource(provides=None))) == []

    def test_a_listing_plex_will_not_give_is_reported(self):
        account = MagicMock()
        account.resources.side_effect = RuntimeError("401 unauthorized")

        with pytest.raises(PlexLinkError, match="Could not list Plex servers"):
            self.listed(account)


class TestResolve:
    def account(self, found=None, error: Exception | None = None) -> MagicMock:
        """A `MyPlexAccount` stand-in answering `resource(server_id)`."""
        stand_in = MagicMock()
        if error is not None:
            stand_in.resource.side_effect = error
        else:
            stand_in.resource.return_value = found
        return stand_in

    def resolved(self, account, connection, server_id: str = "abc123"):
        with (
            patch.object(PlexServers, "account", new_callable=PropertyMock, return_value=account),
            patch("backend.plex.link.PlexConnection", connection),
        ):
            return servers().resolve(server_id, "Music")

    def test_the_first_address_that_answers_is_kept(self):
        """Ordered local, then remote, then relay: the first is the fastest."""
        found = resource(connections=("http://local:32400", "http://remote:32400"))

        opened = self.resolved(self.account(found), connecting("http://local:32400"))

        assert opened.url == "http://local:32400"
        assert (opened.server_id, opened.server_name) == ("abc123", "Living Room")

    def test_a_dead_address_is_stepped_over(self):
        """A laptop off the home network reaches the second address, not none."""
        found = resource(connections=("http://local:32400", "http://remote:32400"))

        opened = self.resolved(self.account(found), connecting("http://remote:32400"))

        assert opened.url == "http://remote:32400"

    def test_the_resource_token_is_preferred(self):
        """It diverges from the account token for a server shared with the user."""
        opened = self.resolved(self.account(resource()), connecting("http://local:32400"))

        assert opened.token.get_secret_value() == "resource-token"

    def test_the_account_token_stands_in_when_there_is_none(self):
        found = resource(access_token=None)

        opened = self.resolved(self.account(found), connecting("http://local:32400"))

        assert opened.token.get_secret_value() == "account-token"

    def test_the_library_name_is_proved_here(self):
        """A server that answers with no such library is not a working choice."""
        self.resolved(self.account(resource()), (opened := connecting("http://local:32400")))

        assert opened.call_args.kwargs["music_library"] == "Music"

    def test_a_server_no_address_answers_reports_the_last_refusal(self):
        """A bare "not connected" says nothing; the refusal names what to fix."""
        found = resource(connections=("http://local:32400",))

        with pytest.raises(PlexLinkError, match="refused"):
            self.resolved(self.account(found), connecting())

    def test_a_server_listing_no_address_is_reported(self):
        found = resource(connections=())

        with pytest.raises(PlexLinkError, match="no address"):
            self.resolved(self.account(found), connecting())

    def test_a_server_the_account_cannot_see_is_reported(self):
        with pytest.raises(PlexLinkError, match="not on this account"):
            self.resolved(self.account(error=KeyError("nope")), connecting())
