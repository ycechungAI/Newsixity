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


@pytest.fixture(scope="module")
def xylophone_article_id():
    """Seed one article with a distinctive word so search can find it.

    Module-scoped and defined at module level, not as a class-scoped instance
    method: pytest 10 removes the latter (it breaks because each test gets a new
    instance while the fixture runs once per class). ``upsert_article`` is
    INSERT OR IGNORE, so re-seeding the same guid returns None — hence one
    module-wide seed rather than one per test.
    """
    from app.db.repository import get_all_feeds, upsert_article

    feed = next(f for f in get_all_feeds() if f.url.startswith("http"))
    return upsert_article(
        feed.id,
        {"guid": "shape-test-1", "title": "Xylophone shape test",
         "link": "https://example.com/xylophone", "published_at": "2026-05-01T00:00:00Z",
         "content": "A xylophone appears in this body text."},
        "shape-hash-1",
    )


class TestSearchResultShape:
    """Search returned the repository's snake_case dataclasses inside a plain
    dict, so ArticleCard read feedName/publishedAt/isSaved as undefined —
    no source, no date, never "saved". Same silent-mismatch class as v0.3 §6."""

    @pytest.fixture
    def article_id(self, xylophone_article_id):
        return xylophone_article_id

    def test_articles_are_camel_case_with_highlight(self, client, article_id):
        data = client.get("/api/articles/search", params={"q": "xylophone"}).json()
        [hit] = [a for a in data["articles"] if a["id"] == article_id]
        for key in ("feedName", "publishedAt", "isSaved", "categorySlug"):
            assert key in hit, key
        assert "feed_name" not in hit
        assert "<mark>" in hit["highlight"].lower()

    def test_filters_are_accepted(self, client, article_id):
        params = {"q": "xylophone", "from": "2026-04-01", "to": "2026-05-31", "saved": "false"}
        ids = [a["id"] for a in client.get("/api/articles/search", params=params).json()["articles"]]
        assert article_id in ids
        params["from"] = "2026-06-01"
        ids = [a["id"] for a in client.get("/api/articles/search", params=params).json()["articles"]]
        assert article_id not in ids

    def test_bad_date_rejected(self, client):
        r = client.get("/api/articles/search", params={"q": "x", "from": "yesterday"})
        assert r.status_code == 422
