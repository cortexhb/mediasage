"""Tests for the root page and the frontend mount."""

import pytest
from starlette.testclient import TestClient

from backend.api import create_app
from backend.api.routes.static import Frontend
from backend.version import Version


class TestIndex:
    def test_serves_something(self, client):
        assert client.get("/").status_code == 200

    def test_asset_urls_carry_the_version(self, client):
        """Without it a browser keeps a cached stylesheet across an upgrade."""
        if Frontend.locate() is None:
            return
        body = client.get("/").text
        assert f"/static/style.css?v={Version.current()}" in body
        assert f"/static/app.js?v={Version.current()}" in body

    def test_the_index_itself_is_not_cached(self, client):
        """It carries the versioned URLs, so a cached copy pins the old ones."""
        if Frontend.locate() is None:
            return
        assert client.get("/").headers["cache-control"] == "no-cache"


class TestCacheBusting:
    def test_stamps_every_versioned_asset(self):
        stamped = Frontend.cache_busted(
            '<link href="/static/style.css"><script src="/static/app.js">'
        )
        assert f"/static/style.css?v={Version.current()}" in stamped
        assert f"/static/app.js?v={Version.current()}" in stamped

    def test_leaves_other_urls_alone(self):
        assert Frontend.cache_busted('<img src="/static/logo.png">') == (
            '<img src="/static/logo.png">'
        )


class TestLocate:
    """The API may be deployed without a frontend beside it."""

    def test_missing_index_is_reported_as_none(self, tmp_path):
        assert Frontend(directory=tmp_path).index_html() is None

    def test_the_index_is_stamped_when_present(self, tmp_path):
        (tmp_path / "index.html").write_text('<link href="/static/style.css">')
        html = Frontend(directory=tmp_path).index_html()
        assert html == f'<link href="/static/style.css?v={Version.current()}">'


class TestWithoutAFrontend:
    """The image ships the API alone, so this is the deployed path."""

    @pytest.fixture
    def api_only(self, monkeypatch) -> TestClient:
        """A client over an application built with no frontend beside it.

        Patched before `create_app`: `register_static_routes` resolves the
        directory once, at registration.
        """
        monkeypatch.setattr(Frontend, "locate", classmethod(lambda cls: None))
        return TestClient(create_app())

    def test_the_root_reports_it_rather_than_failing(self, api_only):
        response = api_only.get("/")
        assert response.status_code == 200
        assert "Frontend not found" in response.json()["message"]

    def test_static_is_not_mounted(self, api_only):
        assert api_only.get("/static/app.js").status_code == 404

    def test_the_api_still_answers(self, api_only):
        assert api_only.get("/api/health").status_code == 200

    def test_the_docs_are_still_served(self, api_only):
        """The React port reads the schema from here."""
        assert api_only.get("/openapi.json").status_code == 200
