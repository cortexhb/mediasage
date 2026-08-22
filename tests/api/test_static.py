"""Tests for the root page and the frontend mount."""

from backend.api.routes import static
from backend.version import get_version


class TestIndex:
    def test_serves_something(self, client):
        assert client.get("/").status_code == 200

    def test_asset_urls_carry_the_version(self, client):
        """Without it a browser keeps a cached stylesheet across an upgrade."""
        if static.frontend_dir() is None:
            return
        body = client.get("/").text
        assert f"/static/style.css?v={get_version()}" in body
        assert f"/static/app.js?v={get_version()}" in body

    def test_the_index_itself_is_not_cached(self, client):
        """It carries the versioned URLs, so a cached copy pins the old ones."""
        if static.frontend_dir() is None:
            return
        assert client.get("/").headers["cache-control"] == "no-cache"


class TestCacheBusting:
    def test_stamps_every_versioned_asset(self):
        stamped = static._cache_busted('<link href="/static/style.css"><script src="/static/app.js">')
        assert f"/static/style.css?v={get_version()}" in stamped
        assert f"/static/app.js?v={get_version()}" in stamped

    def test_leaves_other_urls_alone(self):
        assert static._cache_busted('<img src="/static/logo.png">') == '<img src="/static/logo.png">'
