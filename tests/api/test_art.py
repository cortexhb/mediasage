"""Tests for album art proxy caching.

Without cache headers the browser refetches every cover on each render, and
each hit costs a Plex fetchItem round trip plus the image transfer.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.routes import art as art_module
from backend.config.store import config_store
from tests.api.conftest import mediasage_config


@pytest.fixture
def plex_art():
    """Wire a connected Plex client serving one track thumb."""
    plex = MagicMock()
    plex.is_connected.return_value = True
    plex.thumb_path.return_value = "/library/metadata/1/thumb/1699999999"

    config = mediasage_config(plex_url="http://plex:32400", plex_token="token")

    upstream = MagicMock()
    upstream.status_code = 200
    upstream.content = b"JPEGBYTES"
    upstream.headers = {"content-type": "image/jpeg"}

    store = MagicMock()
    store.get.return_value = plex

    http = MagicMock()
    http.get = AsyncMock(return_value=upstream)

    with (
        patch("backend.api.guards.plex_store", store),
        patch("backend.config.store.ConfigStore.get", return_value=config),
        patch("backend.api.clients.art", AsyncMock(return_value=http)),
    ):
        yield plex, http


class TestArtCacheHeaders:
    def test_serves_image(self, client, plex_art):
        response = client.get("/api/art/1")

        assert response.status_code == 200
        assert response.content == b"JPEGBYTES"
        assert response.headers["content-type"] == "image/jpeg"

    def test_sets_cache_control(self, client, plex_art):
        response = client.get("/api/art/1")
        expected = art_module.cache_control(
            art_module.settings().cache_max_age, immutable=True
        )
        assert response.headers["cache-control"] == expected

    def test_cache_control_is_long_lived(self, client, plex_art):
        response = client.get("/api/art/1")
        cache_control = response.headers["cache-control"]
        assert "public" in cache_control
        assert f"max-age={art_module.settings().cache_max_age}" in cache_control

    def test_the_cache_age_follows_the_configuration(self, client, plex_art, monkeypatch):
        installed = config_store.get()
        monkeypatch.setattr(config_store, "config", installed.model_copy(update={
            "art": installed.art.model_copy(update={"cache_max_age": 60})
        }))

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

        plex.thumb_path.return_value = "/library/metadata/1/thumb/1800000000"
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
        plex.thumb_path.return_value = None

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

    with patch("backend.api.clients.art", AsyncMock(return_value=http)):
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

        expected = art_module.settings().external_cache_max_age
        assert response.headers["cache-control"] == f"public, max-age={expected}"

    def test_refuses_http(self, client, external_art):
        assert client.get(
            "/api/external-art", params={"url": "http://archive.org/x.jpg"}
        ).status_code == 400

    def test_refuses_a_host_off_the_allowlist(self, client, external_art):
        assert client.get(
            "/api/external-art", params={"url": "https://evil.test/x.jpg"}
        ).status_code == 400

    def test_the_allowlist_is_configurable(self, client, external_art, monkeypatch):
        """A deployment mirroring cover art needs its own host allowed."""
        installed = config_store.get()
        monkeypatch.setattr(config_store, "config", installed.model_copy(update={
            "art": installed.art.model_copy(update={"external_domains": ["art.lan"]})
        }))

        assert client.get(
            "/api/external-art", params={"url": "https://art.lan/x.jpg"}
        ).status_code == 200
        assert client.get("/api/external-art", params={"url": CDN}).status_code == 400

    def test_it_follows_a_redirect_inside_the_allowlist(self, client, external_art):
        http, image = external_art
        http.get = AsyncMock(side_effect=[moved(CDN), image])

        assert client.get(
            "/api/external-art", params={"url": "https://coverartarchive.org/release/1/front"}
        ).status_code == 200

    def test_it_refuses_a_redirect_off_the_allowlist(self, client, external_art):
        """An open redirect would otherwise make this a proxy for anything."""
        http, _ = external_art
        http.get = AsyncMock(return_value=moved("https://evil.test/x.jpg"))

        assert client.get("/api/external-art", params={"url": CDN}).status_code == 404

    def test_it_gives_up_past_the_hop_limit(self, client, external_art, monkeypatch):
        installed = config_store.get()
        monkeypatch.setattr(config_store, "config", installed.model_copy(update={
            "art": installed.art.model_copy(update={"max_redirects": 2})
        }))
        http, _ = external_art
        http.get = AsyncMock(return_value=moved(CDN))

        assert client.get("/api/external-art", params={"url": CDN}).status_code == 404
        assert http.get.await_count == 2
