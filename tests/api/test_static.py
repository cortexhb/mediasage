"""Tests for serving the vite build and its client-side routes."""

import pytest
from starlette.testclient import TestClient

from backend.api import create_app
from backend.api.routes.static import Frontend


@pytest.fixture
def built(tmp_path, monkeypatch) -> TestClient:
    """A client over an application serving a miniature build.

    Patched before `create_app`: the directory is resolved once, at
    registration.
    """
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)")
    (tmp_path / "icons").mkdir()
    (tmp_path / "icons" / "brain.svg").write_text("<svg/>")
    (tmp_path / "index.html").write_text("<div id=root></div>")
    monkeypatch.setattr(Frontend, "locate", classmethod(lambda cls: Frontend(directory=tmp_path)))
    return TestClient(create_app())


class TestServingTheBuild:
    def test_the_root_is_the_index(self, built):
        assert built.get("/").text == "<div id=root></div>"

    def test_the_index_itself_is_not_cached(self, built):
        """It names the hashed bundles, so a held copy pins the old ones."""
        assert built.get("/").headers["cache-control"] == "no-cache"

    def test_a_hashed_bundle_is_kept_forever(self, built):
        response = built.get("/assets/index-abc123.js")

        assert response.status_code == 200
        assert "immutable" in response.headers["cache-control"]

    def test_an_unhashed_file_is_revalidated_instead(self, built):
        """A name vite did not hash can be replaced by a later build."""
        response = built.get("/icons/brain.svg")

        assert response.status_code == 200
        assert "cache-control" not in response.headers


class TestClientSideRoutes:
    """Every path the app routes itself must survive a reload."""

    @pytest.mark.parametrize("path", ["/settings", "/result/abc-123", "/playlist/prompt"])
    def test_an_app_route_is_answered_with_the_index(self, built, path):
        response = built.get(path)

        assert response.status_code == 200
        assert response.text == "<div id=root></div>"

    def test_an_unknown_api_path_is_still_a_404(self, built):
        """Answered with the index, a mistyped fetch would parse HTML as JSON."""
        assert built.get("/api/nonsense").status_code == 404

    def test_a_real_api_route_is_not_shadowed(self, built):
        assert built.get("/api/health").status_code == 200

    def test_the_docs_are_not_shadowed(self, built):
        assert built.get("/openapi.json").status_code == 200


class TestFile:
    """What the catch-all is allowed to read off the disk."""

    def test_a_traversal_reads_nothing_outside_the_build(self, tmp_path):
        (tmp_path / "build").mkdir()
        (tmp_path / "secret.env").write_text("token")

        assert Frontend(directory=tmp_path / "build").file("../secret.env") is None

    def test_a_directory_is_not_a_file(self, tmp_path):
        (tmp_path / "assets").mkdir()

        assert Frontend(directory=tmp_path).file("assets") is None

    def test_a_missing_path_is_none(self, tmp_path):
        assert Frontend(directory=tmp_path).file("nope.js") is None


class TestWithoutABuild:
    """Deploying the API alone stays supported."""

    @pytest.fixture
    def api_only(self, monkeypatch) -> TestClient:
        monkeypatch.setattr(Frontend, "locate", classmethod(lambda cls: None))
        return TestClient(create_app())

    def test_the_root_reports_it_rather_than_failing(self, api_only):
        response = api_only.get("/")

        assert response.status_code == 200
        assert "Frontend not found" in response.json()["message"]

    def test_a_missing_index_reports_the_same(self, tmp_path, monkeypatch):
        """An empty directory beside the API is not a build."""
        monkeypatch.setattr(
            Frontend, "locate", classmethod(lambda cls: Frontend(directory=tmp_path))
        )

        assert "Frontend not found" in TestClient(create_app()).get("/").json()["message"]

    def test_the_api_still_answers(self, api_only):
        assert api_only.get("/api/health").status_code == 200
