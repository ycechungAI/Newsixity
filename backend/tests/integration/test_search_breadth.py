"""Search links + federated results (v0.4 §2a/§2b)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.lib.integrations import remote_search
from app.main import app


@pytest.fixture
def client():
    return TestClient(app, base_url="http://localhost")


class TestSearchLinks:
    def test_defaults_then_round_trip(self, client):
        assert len(client.get("/api/search-links").json()["links"]) >= 1
        links = [{"name": " My  Wiki ", "template": "https://wiki.example/search?q={q}"}]
        r = client.put("/api/search-links", json={"links": links})
        assert r.status_code == 200
        assert client.get("/api/search-links").json()["links"] == [
            {"name": "My Wiki", "template": "https://wiki.example/search?q={q}"}
        ]

    @pytest.mark.parametrize("template", [
        "https://no-placeholder.example/",
        "https://twice.example/{q}/{q}",
        "javascript:alert('{q}')",
        "file:///etc/{q}",
    ])
    def test_bad_templates_rejected(self, client, template):
        r = client.put("/api/search-links", json={"links": [{"name": "x", "template": template}]})
        assert r.status_code == 422

    def test_empty_list_allowed(self, client):
        assert client.put("/api/search-links", json={"links": []}).status_code == 200
        assert client.get("/api/search-links").json()["links"] == []


class TestRemoteSearch:
    def test_failure_degrades_to_empty_results(self, client, monkeypatch):
        def boom(q):
            raise TimeoutError("slow")

        monkeypatch.setitem(remote_search.PROVIDERS, "hackernews", boom)
        r = client.get("/api/search/remote", params={"q": "rust"})
        assert r.status_code == 200
        assert r.json()["results"] == [] and r.json()["error"]

    def test_unknown_provider(self, client):
        body = client.get("/api/search/remote", params={"q": "x", "provider": "nope"}).json()
        assert body["results"] == [] and body["error"]


class TestHackerNewsParsing:
    def test_maps_hits_and_sanitises_urls(self, monkeypatch):
        payload = {"hits": [
            {"objectID": "1", "title": "Story", "url": "https://blog.example/post",
             "points": 10, "num_comments": 3, "created_at": "2026-10-01T00:00:00Z"},
            {"objectID": "2", "title": "Ask HN: thing?", "url": None},
            {"objectID": "3", "title": "Evil", "url": "javascript:alert(1)"},
            {"objectID": "4", "title": "", "url": "https://x.example"},
        ]}
        seen = {}

        def fake_fetch(url, timeout):
            seen["url"], seen["timeout"] = url, timeout
            return json.dumps(payload).encode()

        monkeypatch.setattr(remote_search, "fetch_feed_bytes", fake_fetch)
        results = remote_search.search_hacker_news("rust lang")

        assert seen["url"].startswith(remote_search.HN_SEARCH_URL)
        assert "query=rust+lang" in seen["url"]
        assert seen["timeout"] == remote_search.REMOTE_TIMEOUT_SECONDS
        assert [r.url for r in results] == [
            "https://blog.example/post",
            "https://news.ycombinator.com/item?id=2",
            "https://news.ycombinator.com/item?id=3",
        ]
        assert results[0].points == 10 and results[0].comments == 3
