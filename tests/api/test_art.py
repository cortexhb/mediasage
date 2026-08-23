"""Tests for album art proxy caching.

Without cache headers the browser refetches every cover on each render, and
each hit costs a Plex fetchItem round trip plus the image transfer.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.routes.art import CachePolicy, ExternalArt
from backend.config.models import ArtConfig
from backend.config.store import config_store
from tests.api.conftest import mediasage_config, serve_plex


@pytest.fixture
def plex_art(client, monkeypatch):
    """Wire a connected Plex client serving one track thumb."""
    plex = MagicMock()
    plex.connection.is_connected.return_value = True
    plex.library.thumb_path.return_value = "/library/metadata/1/thumb/1699999999"

    config = mediasage_config(plex_url="http://plex:32400", plex_token="token")

    upstream = MagicMock()
    upstream.status_code = 200
    upstream.content = b"JPEGBYTES"
    upstream.headers = {"content-type": "image/jpeg"}

    http = MagicMock()
    http.get = AsyncMock(return_value=upstream)

    serve_plex(client.app, monkeypatch, plex)
    with (
        patch("backend.config.store.ConfigStore.get", return_value=config),
        patch("backend.api.clients.shared.art", AsyncMock(return_value=http)),
    ):
        yield plex, http
    client.app.dependency_overrides.clear()


class TestArtCacheHeaders:
    def test_serves_image(self, client, plex_art):
        response = client.get("/api/art/1")

        assert response.status_code == 200
        assert response.content == b"JPEGBYTES"
        assert response.headers["content-type"] == "image/jpeg"

    def test_sets_cache_control(self, client, plex_art):
        response = client.get("/api/art/1")
        expected = CachePolicy(max_age=config_store.get().art.cache_max_age, immutable=True)
        assert response.headers["cache-control"] == expected.header

    def test_cache_control_is_long_lived(self, client, plex_art):
        response = client.get("/api/art/1")
        cache_control = response.headers["cache-control"]
        assert "public" in cache_control
        assert f"max-age={config_store.get().art.cache_max_age}" in cache_control

    def test_the_cache_age_follows_the_configuration(self, client, plex_art, monkeypatch):
        installed = config_store.get()
        monkeypatch.setattr(
            config_store,
            "config",
            installed.model_copy(
                update={"art": installed.art.model_copy(update={"cache_max_age": 60})}
            ),
        )

        assert "max-age=60" in client.get("/api/art/1").headers["cache-control"]

    def test_sets_etag(self, client, plex_art):
        response = client.get("/api/art/1")
        assert response.headers["etag"].startswith('"')

    def test_etag_is_stable(self, client, plex_art):
        first = client.get("/api/art/1").headers["etag"]
        second = client.get("/api/art/1").headers["etag"]
        assert first == second

    def test_etag_tracks_thumb_path(self, client, plex_art):
        """Plex mints a new thumb path when art changes; the ETag must follow."""
        plex, _ = plex_art
        first = client.get("/api/art/1").headers["etag"]

        plex.library.thumb_path.return_value = "/library/metadata/1/thumb/1800000000"
        second = client.get("/api/art/1").headers["etag"]

        assert first != second

    def test_matching_etag_returns_304(self, client, plex_art):
        etag = client.get("/api/art/1").headers["etag"]

        response = client.get("/api/art/1", headers={"If-None-Match": etag})

        assert response.status_code == 304
        assert response.content == b""

    def test_304_skips_image_fetch(self, client, plex_art):
        """The point of the 304 is not transferring the image again."""
        _, http = plex_art
        etag = client.get("/api/art/1").headers["etag"]
        http.get.reset_mock()

        client.get("/api/art/1", headers={"If-None-Match": etag})

        http.get.assert_not_called()

    def test_stale_etag_returns_image(self, client, plex_art):
        response = client.get("/api/art/1", headers={"If-None-Match": '"outdated"'})

        assert response.status_code == 200
        assert response.content == b"JPEGBYTES"

    def test_missing_art_is_404(self, client, plex_art):
        plex, _ = plex_art
        plex.library.thumb_path.return_value = None

        assert client.get("/api/art/1").status_code == 404

    def test_rejects_non_numeric_key(self, client, plex_art):
        assert client.get("/api/art/not-a-key").status_code == 400


CDN = "https://ia800123.us.archive.org/front.jpg"


@pytest.fixture
def external_art():
    """Wire the shared art client, returning it so a test can script answers."""
    upstream = MagicMock()
    upstream.status_code = 200
    upstream.content = b"JPEGBYTES"
    upstream.headers = {"content-type": "image/jpeg"}

    http = MagicMock()
    http.get = AsyncMock(return_value=upstream)

    with patch("backend.api.clients.shared.art", AsyncMock(return_value=http)):
        yield http, upstream


def moved(location: str) -> MagicMock:
    """An upstream redirect pointing at `location`."""
    answer = MagicMock()
    answer.status_code = 302
    answer.headers = {"location": location}
    return answer


class TestExternalArt:
    """Proxied so the page does not hotlink a CDN, and cannot be aimed anywhere."""

    def test_serves_an_allowed_host(self, client, external_art):
        response = client.get("/api/external-art", params={"url": CDN})

        assert response.status_code == 200
        assert response.content == b"JPEGBYTES"

    def test_sets_a_shorter_cache_than_plex_art(self, client, external_art):
        """External art is not content-addressed, so it gets a day, not a week."""
        response = client.get("/api/external-art", params={"url": CDN})

        expected = config_store.get().art.external_cache_max_age
        assert response.headers["cache-control"] == f"public, max-age={expected}"

    def test_refuses_http(self, client, external_art):
        assert (
            client.get("/api/external-art", params={"url": "http://archive.org/x.jpg"}).status_code
            == 400
        )

    def test_refuses_a_host_off_the_allowlist(self, client, external_art):
        assert (
            client.get("/api/external-art", params={"url": "https://evil.test/x.jpg"}).status_code
            == 400
        )

    def test_the_allowlist_is_configurable(self, client, external_art, monkeypatch):
        """A deployment mirroring cover art needs its own host allowed."""
        installed = config_store.get()
        monkeypatch.setattr(
            config_store,
            "config",
            installed.model_copy(
                update={"art": installed.art.model_copy(update={"external_domains": ["art.lan"]})}
            ),
        )

        assert (
            client.get("/api/external-art", params={"url": "https://art.lan/x.jpg"}).status_code
            == 200
        )
        assert client.get("/api/external-art", params={"url": CDN}).status_code == 400

    def test_it_follows_a_redirect_inside_the_allowlist(self, client, external_art):
        http, image = external_art
        http.get = AsyncMock(side_effect=[moved(CDN), image])

        assert (
            client.get(
                "/api/external-art", params={"url": "https://coverartarchive.org/release/1/front"}
            ).status_code
            == 200
        )

    def test_it_refuses_a_redirect_off_the_allowlist(self, client, external_art):
        """An open redirect would otherwise make this a proxy for anything."""
        http, _ = external_art
        http.get = AsyncMock(return_value=moved("https://evil.test/x.jpg"))

        assert client.get("/api/external-art", params={"url": CDN}).status_code == 404

    def test_it_gives_up_past_the_hop_limit(self, client, external_art, monkeypatch):
        installed = config_store.get()
        monkeypatch.setattr(
            config_store,
            "config",
            installed.model_copy(
                update={"art": installed.art.model_copy(update={"max_redirects": 2})}
            ),
        )
        http, _ = external_art
        http.get = AsyncMock(return_value=moved(CDN))

        assert client.get("/api/external-art", params={"url": CDN}).status_code == 404
        assert http.get.await_count == 2


class TestCachePolicy:
    @pytest.mark.parametrize(
        ("policy", "expected"),
        [
            (CachePolicy(max_age=60), "public, max-age=60"),
            (CachePolicy(max_age=0), "public, max-age=0"),
            (CachePolicy(max_age=60, immutable=True), "public, max-age=60, immutable"),
        ],
    )
    def test_header(self, policy, expected):
        assert policy.header == expected

    def test_it_is_frozen(self):
        """A policy is shared across responses; a mutation would leak between them."""
        assert CachePolicy.model_config["frozen"] is True


class TestExternalArtAllowlist:
    """The allowlist is the containment: nothing off it is fetched, ever."""

    source = ExternalArt(domains=["coverartarchive.org", "archive.org"], max_redirects=5)

    @pytest.mark.parametrize(
        "url",
        [
            "https://archive.org/x.jpg",
            "https://coverartarchive.org/release/1/front",
            "https://ia800123.us.archive.org/x.jpg",
        ],
    )
    def test_it_allows_the_listed_hosts_and_their_subdomains(self, url):
        assert self.source.allows(url)

    @pytest.mark.parametrize(
        "url",
        [
            "http://archive.org/x.jpg",
            "https://evil.test/x.jpg",
            "https://notarchive.org/x.jpg",
            "https://evilarchive.org/x.jpg",
            "https://archive.org.evil.test/x.jpg",
            "https://127.0.0.1/x.jpg",
            "",
        ],
    )
    def test_it_refuses_everything_else(self, url):
        assert not self.source.allows(url)

    def test_a_lan_mirror_may_be_allowlisted(self):
        """Why this is not SafeFetcher: a private mirror is a valid source."""
        assert ExternalArt(domains=["art.lan"], max_redirects=5).allows("https://art.lan/x.jpg")

    def test_of_reads_the_configuration(self):
        art = ArtConfig(external_domains=["art.lan"], max_redirects=2)
        source = ExternalArt.of(art)

        assert source.domains == ["art.lan"]
        assert source.max_redirects == 2

    def test_it_is_frozen(self):
        """The allowlist is containment; a mutation would widen what may be fetched."""
        assert ExternalArt.model_config["frozen"] is True


class TestExternalArtGet:
    source = ExternalArt(domains=["archive.org"], max_redirects=3)

    async def test_it_returns_the_image(self):
        image = MagicMock(status_code=200)
        client = MagicMock(get=AsyncMock(return_value=image))

        assert await self.source.get(client, CDN) is image

    async def test_it_follows_an_allowed_redirect(self):
        image = MagicMock(status_code=200)
        client = MagicMock(get=AsyncMock(side_effect=[moved(CDN), image]))

        assert await self.source.get(client, "https://archive.org/release/1/front") is image

    async def test_it_stops_at_a_redirect_off_the_allowlist(self):
        client = MagicMock(get=AsyncMock(return_value=moved("https://evil.test/x.jpg")))

        assert await self.source.get(client, CDN) is None
        assert client.get.await_count == 1

    async def test_it_stops_at_a_redirect_with_no_location(self):
        client = MagicMock(get=AsyncMock(return_value=moved("")))

        assert await self.source.get(client, CDN) is None

    async def test_it_gives_up_on_an_upstream_error(self):
        client = MagicMock(get=AsyncMock(return_value=MagicMock(status_code=500)))

        assert await self.source.get(client, CDN) is None
        assert client.get.await_count == 1

    async def test_it_gives_up_past_the_hop_budget(self):
        client = MagicMock(get=AsyncMock(return_value=moved(CDN)))

        assert await self.source.get(client, CDN) is None
        assert client.get.await_count == 3

    async def test_a_zero_hop_budget_fetches_nothing(self):
        client = MagicMock(get=AsyncMock())

        assert await ExternalArt(domains=[], max_redirects=0).get(client, CDN) is None
        client.get.assert_not_awaited()
