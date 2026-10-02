"""POST /api/podcasts through the real app.

No test existed for this route, which is how a missing import shipped: the
handler called ``extract_podcast_episodes`` without importing it, so every
subscribe raised NameError -> 500 -> the UI showed its generic "Failed to
subscribe" fallback with nothing in the log. These tests pin the happy path
(the import regression), the duplicate short-circuit, and the error mapping.
"""

from __future__ import annotations

import feedparser
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import podcasts as podcasts_router

FEED_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Test Show</title>
    <description>A show for tests</description>
    <link>https://show.example/</link>
    <itunes:author>Test Author</itunes:author>
    <image><href>https://show.example/art.png</href></image>
    <item>
      <title>Episode One</title>
      <guid>ep-1</guid>
      <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
      <enclosure url="https://cdn.example/ep1.mp3" type="audio/mpeg" length="1"/>
    </item>
    <item>
      <title>Episode Two</title>
      <guid>ep-2</guid>
      <pubDate>Tue, 02 Jan 2024 00:00:00 GMT</pubDate>
      <enclosure url="https://cdn.example/ep2.mp3" type="audio/mpeg" length="1"/>
    </item>
  </channel>
</rss>
"""


@pytest.fixture
def client():
    return TestClient(app, base_url="http://localhost")


@pytest.fixture
def feed(monkeypatch):
    """Stub the network fetch with a parsed copy of FEED_XML."""
    monkeypatch.setattr(
        podcasts_router, "fetch_podcast_feed", lambda url: feedparser.parse(FEED_XML)
    )


def test_subscribe_creates_feed_and_episodes(client, feed):
    """Regression: this route called extract_podcast_episodes without importing it."""
    r = client.post("/api/podcasts", json={"feed_url": "https://show.example/feed.xml"})
    assert r.status_code == 200, r.text

    body = r.json()
    assert body["title"] == "Test Show"
    assert body["feedUrl"] == "https://show.example/feed.xml"
    assert body["imageUrl"] == "https://show.example/art.png"
    assert any(f["id"] == body["id"] for f in client.get("/api/podcasts").json())

    episodes = client.get(f"/api/podcasts/{body['id']}/episodes").json()
    assert {e["title"] for e in episodes} == {"Episode One", "Episode Two"}


def test_subscribe_is_idempotent(client, feed):
    first = client.post("/api/podcasts", json={"feed_url": "https://dup.example/f.xml"})
    second = client.post("/api/podcasts", json={"feed_url": "https://dup.example/f.xml"})
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert len([f for f in client.get("/api/podcasts").json()
                if f["feedUrl"] == "https://dup.example/f.xml"]) == 1


def test_unsafe_url_is_400_with_reason(client, monkeypatch):
    """A ValueError from the fetcher must surface its detail, not be swallowed."""
    def boom(url):
        raise ValueError("Feed URL must be a valid http/https URL")

    monkeypatch.setattr(podcasts_router, "fetch_podcast_feed", boom)
    r = client.post("/api/podcasts", json={"feed_url": "not-a-url"})
    assert r.status_code == 400
    assert r.json()["detail"] == "Feed URL must be a valid http/https URL"


def test_network_failure_is_400(client, monkeypatch):
    def boom(url):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(podcasts_router, "fetch_podcast_feed", boom)
    assert client.post(
        "/api/podcasts", json={"feed_url": "https://down.example/f.xml"}
    ).status_code == 400


def test_bozo_feed_without_entries_is_rejected(client, monkeypatch):
    """A non-feed page should not be accepted as a podcast."""
    parsed = feedparser.parse(b"<html><body>not a feed</body></html>")
    monkeypatch.setattr(podcasts_router, "fetch_podcast_feed", lambda url: parsed)
    r = client.post("/api/podcasts", json={"feed_url": "https://page.example/"})
    assert r.status_code == 400