"""Integration smoke test for NextExportStaticFiles clean-URL routing.

Boots the real FastAPI `app` (no lifespan, so no DB init / background jobs —
static file serving is wired at module import time in app/main.py, not in
the lifespan) and hits it through TestClient to catch the exact class of bug
the Opus audit found: pytest passing but every non-homepage nav link 404ing.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestCleanUrlPages:
    """Next static-export clean URLs must resolve to their {path}.html file."""

    def test_homepage_serves_index(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_top_level_clean_url(self):
        resp = client.get("/finance")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_nested_clean_url(self):
        resp = client.get("/finance/news")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_settings_page(self):
        assert client.get("/settings").status_code == 200

    def test_saved_page(self):
        assert client.get("/saved").status_code == 200

    def test_console_page(self):
        assert client.get("/console").status_code == 200

    def test_weather_page(self):
        assert client.get("/weather").status_code == 200

    def test_explicit_html_extension_still_works(self):
        resp = client.get("/finance.html")
        assert resp.status_code == 200


class TestUnknownRoutes:
    def test_unknown_path_returns_exported_404_page(self):
        resp = client.get("/this-route-does-not-exist-xyz")
        assert resp.status_code == 404
        assert "text/html" in resp.headers["content-type"]

    def test_unknown_nested_path_returns_404(self):
        resp = client.get("/finance/does-not-exist-xyz")
        assert resp.status_code == 404


class TestStaticAssets:
    """JS/CSS bundles must still be served as exact-path assets, unaffected
    by the clean-URL fallback logic."""

    def test_favicon_served(self):
        resp = client.get("/favicon.ico")
        assert resp.status_code == 200

    def test_js_chunk_served_with_js_content_type(self):
        import pathlib

        out_dir = pathlib.Path(__file__).resolve().parents[3] / "out"
        chunks_dir = out_dir / "_next" / "static" / "chunks"
        js_files = list(chunks_dir.glob("*.js"))
        assert js_files, "expected at least one built JS chunk in out/_next/static/chunks"

        url_path = "/" + str(js_files[0].relative_to(out_dir))
        resp = client.get(url_path)
        assert resp.status_code == 200
        assert "javascript" in resp.headers["content-type"]


class TestApiUnaffected:
    """/api/* must bypass the static-file mount entirely."""

    def test_health_endpoint_not_swallowed_by_static_mount(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")
