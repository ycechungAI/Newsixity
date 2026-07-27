"""Route-level tests for GET /api/articles/search.

The search engine had no HTTP route at all before this — search_articles()
existed and was correct but nothing could reach it, and the top-bar search
box submitted to a query parameter no page read.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app, base_url="http://localhost")


class TestSearchRoute:
    def test_search_route_is_not_shadowed_by_the_article_id_route(self, client):
        """/articles/search must not be parsed as /articles/{article_id}.

        FastAPI matches in definition order, and /articles/{article_id} is
        declared in the same router. If search were registered after it,
        "search" would be coerced to an int and fail with 422.
        """
        resp = client.get("/api/articles/search", params={"q": "anything"})
        assert resp.status_code == 200, resp.text
        assert "articles" in resp.json()

    def test_returns_query_count_and_articles(self, client):
        data = client.get("/api/articles/search", params={"q": "test"}).json()
        assert data["query"] == "test"
        assert data["count"] == len(data["articles"])

    def test_missing_query_is_rejected(self, client):
        assert client.get("/api/articles/search").status_code == 422

    def test_empty_query_is_rejected(self, client):
        assert client.get("/api/articles/search", params={"q": ""}).status_code == 422

    def test_hostile_queries_do_not_500(self, client):
        """FTS5 syntax in user input must never reach MATCH unescaped."""
        for q in ['" OR "', "*", "AND OR NOT", "NEAR/3 x", "col:value", "a\"b", "'; DROP TABLE articles;--"]:
            resp = client.get("/api/articles/search", params={"q": q})
            assert resp.status_code == 200, f"{q!r} -> {resp.status_code} {resp.text}"

    def test_limit_is_bounded(self, client):
        assert client.get("/api/articles/search", params={"q": "a", "limit": 9999}).status_code == 422
        assert client.get("/api/articles/search", params={"q": "a", "limit": 0}).status_code == 422

    def test_articles_still_reachable_by_id(self, client):
        """Adding the search route must not break the id route beside it."""
        resp = client.get("/api/articles/999999999")
        assert resp.status_code in (404, 200)  # not 422 — the path still parses as an int
