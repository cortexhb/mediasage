"""Tests for ``/api/plex`` -- the pin exchange, the picker, and signing out.

The sign-in is the only writer of the Plex identity, so what each route keeps
matters as much as what it answers: a token that reaches the response but not
`config.user.yaml` is a sign-in that does not survive a restart.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from backend.config import ConfigSaveError
from backend.models import PlexServerChoice
from backend.plex.link import PlexLinkError, PlexPin, PlexResolution
from tests.api.conftest import mediasage_config


@pytest.fixture
def kept():
    """Capture what a route commits, and hand its result back as the config.

    Patched at `ConfigStore.commit` rather than at the file: the routes are
    what is under test, and the store's own writing has its own tests.
    """
    with patch("backend.config.store.ConfigStore.commit") as commit:
        commit.side_effect = lambda change: change.config
        yield commit


@pytest.fixture(autouse=True)
def rebuilt(plex, rebuilds):
    """Make the client a chosen server rebuilds the one the fixture serves.

    Choosing a server writes `plex_store.client` itself, so the response is
    read off whatever the rebuild returned rather than off the override.
    """
    rebuilds.plex.return_value = plex
    return plex


def sections(commit) -> dict:
    """The Plex keys the last commit would have written."""
    return commit.call_args.args[0].sections.get("plex", {})


def pin(
    identifier: int = 42,
    code: str = "WXYZ",
    url: str = "https://app.plex.tv/auth/#!?code=WXYZ",
    expires_in: int = 900,
) -> PlexPin:
    """A pin as `PlexLink.begin` would hand one back."""
    return PlexPin(id=identifier, code=code, url=url, expires_in=expires_in)


def linking():
    """Patch `PlexLink` so the routes get a scripted sign-in helper.

    `begin` and `claim` are awaited, so both are `AsyncMock`; `identity` is
    read as a plain attribute.
    """
    stand_in = MagicMock(begin=AsyncMock(), claim=AsyncMock())
    return patch("backend.api.routes.plex.link.PlexLink.of", return_value=stand_in)


def listing(*choices, error: Exception | None = None):
    """Patch `PlexServers` so the routes get a scripted server list."""
    stand_in = MagicMock()
    if error is not None:
        stand_in.choices.side_effect = error
    else:
        stand_in.choices.return_value = list(choices)
    return patch("backend.api.routes.plex.link.PlexServers", return_value=stand_in)


def choice(identifier: str = "abc123", name: str = "Living Room") -> PlexServerChoice:
    return PlexServerChoice(id=identifier, name=name, owned=True)


def resolving(resolution=None, error: Exception | None = None):
    """Patch `PlexServers.resolve` with what choosing a server would find."""
    stand_in = MagicMock()
    if error is not None:
        stand_in.resolve.side_effect = error
    else:
        stand_in.resolve.return_value = resolution
    return patch("backend.api.routes.plex.link.PlexServers", return_value=stand_in)


RESOLVED = PlexResolution(
    url="http://local:32400",
    token=SecretStr("resource-token"),
    server_id="abc123",
    server_name="Living Room",
)


def configured(**overrides):
    """Serve one configuration to every route under test."""
    return patch("backend.config.store.ConfigStore.get", return_value=mediasage_config(**overrides))


class TestBegin:
    def test_a_pin_reaches_the_browser(self, client, plex, kept):
        with configured(client_id="stored"), linking() as of:
            of.return_value.begin.return_value = pin()
            of.return_value.identity.client_id = "stored"
            data = client.post("/api/plex/link").json()

        assert (data["pin_id"], data["code"], data["expires_in"]) == (42, "WXYZ", 900)
        assert "code=WXYZ" in data["url"]

    def test_a_new_identifier_is_written_before_it_is_used(self, client, plex, kept):
        """A pin approved under one identifier cannot be claimed under another."""
        with configured(client_id=""), linking() as of:
            of.return_value.begin.return_value = pin()
            of.return_value.identity.client_id = "minted"
            client.post("/api/plex/link")

        assert sections(kept) == {"client_id": "minted"}

    def test_a_stored_identifier_is_written_again(self, client, plex, kept):
        """Rewriting it every sign-in would churn the file for no change."""
        with configured(client_id="stored"), linking() as of:
            of.return_value.begin.return_value = pin()
            of.return_value.identity.client_id = "stored"
            client.post("/api/plex/link")

        kept.assert_not_called()

    def test_a_plex_tv_refusal_is_a_bad_gateway(self, client, plex, kept):
        """Not a 500: the failure is upstream, and the form says so."""
        with configured(), linking() as of:
            of.return_value.begin.side_effect = PlexLinkError("Could not reach plex.tv")
            response = client.post("/api/plex/link")

        assert response.status_code == 502
        assert "plex.tv" in response.json()["detail"]


class TestPoll:
    def test_an_unapproved_pin_is_pending(self, client, plex, kept):
        with configured(), linking() as of:
            of.return_value.claim.return_value = None
            data = client.get("/api/plex/link/42").json()

        assert data["state"] == "pending"
        kept.assert_not_called()

    def test_an_approved_pin_stores_the_account_token(self, client, plex, kept):
        """Stored before a server is chosen: it is what survives a closed tab."""
        with configured(), linking() as of, listing(choice()):
            of.return_value.claim.return_value = SecretStr("account-token")
            data = client.get("/api/plex/link/42").json()

        assert data["state"] == "linked"
        assert sections(kept) == {"account_token": "account-token"}

    def test_the_token_is_unwrapped_for_the_file(self, client, plex, kept):
        """Left wrapped, yaml writes a python-object tag nothing can read back."""
        with configured(), linking() as of, listing(choice()):
            of.return_value.claim.return_value = SecretStr("account-token")
            client.get("/api/plex/link/42")

        assert isinstance(sections(kept)["account_token"], str)

    def test_the_servers_are_listed_with_it(self, client, plex, kept):
        with configured(), linking() as of, listing(choice(), choice("def456", "Attic")):
            of.return_value.claim.return_value = SecretStr("account-token")
            data = client.get("/api/plex/link/42").json()

        assert [one["name"] for one in data["servers"]] == ["Living Room", "Attic"]

    def test_a_listing_that_fails_still_leaves_the_user_signed_in(self, client, plex, kept):
        """The token is already stored; the UI offers a retry, not a new pin."""
        with (
            configured(),
            linking() as of,
            listing(error=PlexLinkError("Could not list Plex servers")),
        ):
            of.return_value.claim.return_value = SecretStr("account-token")
            data = client.get("/api/plex/link/42").json()

        assert (data["state"], data["servers"]) == ("linked", [])

    def test_an_unknown_pin_is_a_bad_gateway(self, client, plex, kept):
        with configured(), linking() as of:
            of.return_value.claim.side_effect = PlexLinkError("Plex refused the request: 404")
            assert client.get("/api/plex/link/42").status_code == 502

    def test_a_failed_write_is_a_500(self, client, plex):
        """A token that reached memory but not disk is lost on the next restart."""
        with (
            configured(),
            linking() as of,
            patch("backend.config.store.ConfigStore.commit", side_effect=ConfigSaveError("full")),
        ):
            of.return_value.claim.return_value = SecretStr("account-token")
            assert client.get("/api/plex/link/42").status_code == 500


class TestListServers:
    """Where the picker comes back from after a reload mid-sign-in."""

    def test_the_servers_are_listed_again(self, client, plex, kept):
        with configured(), listing(choice(), choice("def456", "Attic")):
            data = client.get("/api/plex/servers").json()

        assert [one["id"] for one in data["servers"]] == ["abc123", "def456"]
        kept.assert_not_called()

    def test_listing_before_signing_in_is_a_conflict(self, client, plex, kept):
        with configured(account_token=""):
            assert client.get("/api/plex/servers").status_code == 409

    def test_a_listing_plex_will_not_give_is_empty_rather_than_an_error(self, client, plex, kept):
        """The sign-in still stands; the UI offers a retry."""
        with configured(), listing(error=PlexLinkError("Could not list Plex servers")):
            assert client.get("/api/plex/servers").json()["servers"] == []


class TestChooseServer:
    def choose(self, client, identifier: str = "abc123"):
        return client.post("/api/plex/server", json={"server_id": identifier})

    def test_the_resolved_address_and_token_are_kept(self, client, plex, kept):
        with configured(), resolving(RESOLVED):
            self.choose(client)

        assert sections(kept) == {
            "url": "http://local:32400",
            "token": "resource-token",
            "server_id": "abc123",
            "server_name": "Living Room",
        }

    def test_the_card_reports_what_is_now_in_force(self, client, plex, kept):
        plex.connection.music_libraries.return_value = ["Music", "Podcasts"]

        with configured(), resolving(RESOLVED):
            data = self.choose(client).json()

        assert (data["linked"], data["connected"]) == (True, True)
        assert (data["server_name"], data["server_id"]) == ("Living Room", "abc123")
        assert data["music_libraries"] == ["Music", "Podcasts"]

    def test_the_client_is_rebuilt_onto_the_new_server(self, client, plex, kept, rebuilds):
        """Without it every later request would still read the old one."""
        with configured(), resolving(RESOLVED):
            self.choose(client)

        rebuilds.plex.assert_called_once()

    def test_a_server_that_will_not_answer_keeps_the_previous_one(self, client, plex, kept):
        """Nothing is written: a server that is off must not unconfigure the app."""
        with configured(), resolving(error=PlexLinkError("Plex listed no address")):
            response = self.choose(client)

        assert response.status_code == 422
        assert "no address" in response.json()["detail"]
        kept.assert_not_called()

    def test_choosing_before_signing_in_is_a_conflict(self, client, plex, kept):
        """Not a 401: there is no credential to reject, only a step skipped."""
        with configured(account_token=""):
            response = self.choose(client)

        assert response.status_code == 409

    def test_the_configured_library_name_is_what_is_proved(self, client, plex, kept):
        with configured(music_library="Vinyl Rips"), resolving(RESOLVED) as servers:
            self.choose(client)

        assert servers.return_value.resolve.call_args.args == ("abc123", "Vinyl Rips")


class TestForget:
    def test_the_identity_is_cleared(self, client, plex, kept):
        with configured():
            data = client.delete("/api/plex/link").json()

        assert sections(kept) == {
            "account_token": "",
            "token": "",
            "server_id": "",
            "server_name": "",
            "url": "",
        }
        assert data["linked"] is False

    def test_the_client_identifier_is_kept(self, client, plex, kept):
        """Reused, signing back in reuses the device already in the account."""
        with configured(client_id="stored"):
            client.delete("/api/plex/link")

        assert "client_id" not in sections(kept)

    def test_nothing_is_connected_afterwards(self, client, plex, kept):
        with configured():
            data = client.delete("/api/plex/link").json()

        assert (data["connected"], data["music_libraries"]) == (False, [])
