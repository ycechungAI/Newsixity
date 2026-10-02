"""POST/PATCH/DELETE /api/feeds (v0.4 §1) through the real app.

The network is stubbed at probe_feed (its SSRF and parse behaviour is pinned
in test_rss_fetch.py); these tests pin what the routes do with its answer.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.lib.integrations.rss import FeedProbe, UnsafeFeedUrlError
from app.main import app
from app.routers import feeds as feeds_router


@pytest.fixture
def client():
    return TestClient(app, base_url="http://localhost")


@pytest.fixture
def probe(monkeypatch):
    """Make probe_feed accept any URL as a feed titled 'Probe Title'."""
    def fake(url):
        return FeedProbe(url=url, title="Probe Title", entry_count=3)

    monkeypatch.setattr(feeds_router, "probe_feed", fake)


def _create(client, url, **extra):
    return client.post("/api/feeds", json={"url": url, "categorySlug": "technology", **extra})


class TestCreate:
    def test_creates_with_probed_title(self, client, probe):
        r = _create(client, "https://crud.example/a.xml")
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["name"] == "Probe Title"
        assert body["categorySlug"] == "technology"
        assert body["enabled"] is True
        assert any(f["id"] == body["id"] for f in client.get("/api/feeds").json())

    def test_explicit_name_wins(self, client, probe):
        r = _create(client, "https://crud.example/b.xml", name="My Feed")
        assert r.json()["name"] == "My Feed"

    def test_duplicate_is_409(self, client, probe):
        _create(client, "https://crud.example/c.xml")
        assert _create(client, "https://crud.example/c.xml").status_code == 409

    def test_unknown_category_is_400(self, client, probe):
        r = client.post("/api/feeds", json={"url": "https://crud.example/d.xml", "categorySlug": "nope"})
        assert r.status_code == 400

    def test_unsafe_url_rejected_with_reason(self, client, monkeypatch):
        def unsafe(url):
            raise UnsafeFeedUrlError("Feed URL resolves to a blocked address")

        monkeypatch.setattr(feeds_router, "probe_feed", unsafe)
        r = _create(client, "http://127.0.0.1/feed")
        assert r.status_code == 400
        assert "blocked" in r.json()["detail"]

    def test_not_a_feed_rejected_with_reason(self, client, monkeypatch):
        def html(url):
            raise ValueError("That URL did not return an RSS or Atom feed")

        monkeypatch.setattr(feeds_router, "probe_feed", html)
        r = _create(client, "https://crud.example/page.html")
        assert r.status_code == 400 and "RSS" in r.json()["detail"]


class TestUpdateAndDelete:
    def test_disable_rename_and_move(self, client, probe):
        feed_id = _create(client, "https://crud.example/e.xml").json()["id"]
        r = client.patch(f"/api/feeds/{feed_id}",
                         json={"enabled": False, "name": "Renamed", "categorySlug": "gaming"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert (body["enabled"], body["name"], body["categorySlug"]) == (False, "Renamed", "gaming")

    def test_delete(self, client, probe):
        feed_id = _create(client, "https://crud.example/f.xml").json()["id"]
        r = client.delete(f"/api/feeds/{feed_id}")
        assert r.status_code == 200 and r.json()["success"] is True
        assert all(f["id"] != feed_id for f in client.get("/api/feeds").json())
        assert client.delete(f"/api/feeds/{feed_id}").status_code == 404

    def test_manual_links_feed_is_protected(self, client):
        manual = next(f for f in client.get("/api/feeds").json() if f["url"] == "internal://manual")
        assert client.delete(f"/api/feeds/{manual['id']}").status_code == 403
        assert client.patch(f"/api/feeds/{manual['id']}", json={"enabled": False}).status_code == 403

    def test_literal_routes_not_shadowed(self, client):
        # /feeds/weights must still be the weights route, not feed_id="weights".
        assert client.get("/api/feeds/weights").status_code == 200
