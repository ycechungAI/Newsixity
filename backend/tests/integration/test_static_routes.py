"""Integration smoke test for SPAStaticFiles fallback routing.

Boots the real FastAPI `app` (no lifespan, so no DB init / background jobs —
static file serving is wired at module import time in app/main.py, not in
the lifespan) and hits it through TestClient to catch the exact class of bug
the Opus audit found: pytest passing but every non-homepage nav link 404ing.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestCleanUrlPages:
    """Client-side routes (React Router) must fall back to index.html."""

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

    def test_dynamic_article_route(self):
        """/article/:id is a path param — no build-time enumeration needed."""
        resp = client.get("/article/12345")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


class TestUnknownRoutes:
    """Unknown paths still get index.html (200), not a server 404 — React
    Router's own NotFoundPage decides what the user sees."""

    def test_unknown_path_falls_back_to_index(self):
        resp = client.get("/this-route-does-not-exist-xyz")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_unknown_nested_path_falls_back_to_index(self):
        resp = client.get("/finance/does-not-exist-xyz")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


class TestStaticAssets:
    """JS/CSS bundles must still be served as exact-path assets, unaffected
    by the SPA-fallback logic."""

    def test_favicon_served(self):
        resp = client.get("/favicon.ico")
        assert resp.status_code == 200

    def test_js_chunk_served_with_js_content_type(self):
        import pathlib

        dist_dir = pathlib.Path(__file__).resolve().parents[3] / "dist"
        assets_dir = dist_dir / "assets"
        js_files = list(assets_dir.glob("*.js"))
        assert js_files, "expected at least one built JS chunk in dist/assets"

        url_path = "/" + str(js_files[0].relative_to(dist_dir))
        resp = client.get(url_path)
        assert resp.status_code == 200
        assert "javascript" in resp.headers["content-type"]


class TestApiUnaffected:
    """/api/* must bypass the static-file mount entirely."""

    def test_health_endpoint_not_swallowed_by_static_mount(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")
