"""§1 - ranking must order the live article list.

Before this, the scoring pipeline wrote relevance_score but nothing read it:
every list endpoint ordered by published_at DESC, so the score column had zero
effect on what the user saw. This pins the three sort modes on /api/articles.
"""

from __future__ import annotations

import pytest

from app.db.init_db import init_db
from app.db.repository import (
    create_feed,
    get_articles_by_category,
    update_article_scores,
    upsert_article,
)


@pytest.fixture(scope="module", autouse=True)
def _db():
    init_db()
    yield


@pytest.fixture
def client():
    from starlette.testclient import TestClient

    from app.main import app

    return TestClient(app, base_url="http://localhost")


def _seed():
    import time
    feed = create_feed(f"https://sort.test/{time.time_ns()}.xml", "Sort Feed", "technology")
    older_scored = upsert_article(
        feed.id,
        {"guid": "sort-old-scored", "title": "Sorted old scored", "link": "https://sort.test/a",
         "published_at": "2026-01-01T00:00:00Z", "content": None},
        "sort-old-scored-hash",
    )
    scored = upsert_article(
        feed.id,
        {"guid": "sort-new-scored", "title": "Sorted new scored", "link": "https://sort.test/b",
         "published_at": "2026-09-30T00:00:00Z", "content": None},
        "sort-new-scored-hash",
    )
    fresh = upsert_article(
        feed.id,
        {"guid": "sort-fresh-plain", "title": "Sorted fresh plain", "link": "https://sort.test/c",
         "published_at": "2026-10-02T00:00:00Z", "content": None},
        "sort-fresh-plain-hash",
    )
    update_article_scores([{"id": older_scored, "score": 95.0}])
    update_article_scores([{"id": scored, "score": 60.0}])
    # `fresh` keeps its default 0 score — the unscored tail case.
    return feed.id, older_scored, scored, fresh


def test_relevance_orders_scored_then_unscored_by_recency(client):
    feed_id, old_scored, new_scored, fresh = _seed()

    data = client.get("/api/articles", params={"category": "technology", "sort": "relevance"}).json()
    ids = [a["id"] for a in data]
    assert ids.index(old_scored) < ids.index(new_scored) < ids.index(fresh), ids


def test_recent_is_recency_only(client):
    feed_id, old_scored, new_scored, fresh = _seed()

    data = client.get("/api/articles", params={"category": "technology", "sort": "recent"}).json()
    ids = [a["id"] for a in data]
    assert ids.index(fresh) < ids.index(new_scored) < ids.index(old_scored), ids


def test_source_orders_by_feed_name(client):
    feed_id, old_scored, new_scored, fresh = _seed()

    data = client.get("/api/articles", params={"category": "technology", "sort": "source"}).json()
    # All seed rows share one feed, so within the feed they must be recency-ordered.
    ids = [a["id"] for a in data]
    assert ids.index(fresh) < ids.index(new_scored) < ids.index(old_scored), ids


def test_unknown_sort_falls_back_to_recent_not_500(client):
    feed_id, old_scored, new_scored, fresh = _seed()

    data = client.get("/api/articles", params={"category": "technology", "sort": "banana"}).json()
    assert isinstance(data, list)
    ids = [a["id"] for a in data]
    assert ids.index(fresh) < ids.index(new_scored) < ids.index(old_scored), ids


def test_default_is_relevance(client):
    feed_id, old_scored, new_scored, fresh = _seed()

    data = client.get("/api/articles", params={"category": "technology"}).json()
    ids = [a["id"] for a in data]
    # Default sort must be relevance: old_scored (95) ahead of new_scored (60)
    # even though new_scored is newer. Under recency ordering this would fail.
    assert ids.index(old_scored) < ids.index(new_scored), ids
