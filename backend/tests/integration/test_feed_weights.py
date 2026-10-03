"""GET /api/feeds/weights — the Settings > Feed Rankings read path.

Every feed starts at source_weight 1.0. That value is the case the frontend
got wrong: React matches <select> values as strings, and String(1.0) is "1"
while the option's value is "1.0", so a feed at the default weight matched no
option and the browser displayed the first one (Low). These tests pin the
weight each feed actually reports, so the preset the UI shows is the preset
that was saved.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.repository import create_feed, update_feed_source_weight
from app.main import app


@pytest.fixture
def client():
    return TestClient(app, base_url="http://localhost")


@pytest.fixture
def feeds(request):
    """Two feeds at distinct weights, so the read path is unambiguous.

    URLs are namespaced per test: the session database is shared, so a fixed
    URL would collide as DuplicateFeedError on the second test that uses it.
    """
    tag = request.node.name
    low = create_feed(f"https://rank.example/{tag}/low.xml", f"Rank Low {tag}", "technology")
    high = create_feed(f"https://rank.example/{tag}/high.xml", f"Rank High {tag}", "technology")
    update_feed_source_weight(low.id, 0.5)
    update_feed_source_weight(high.id, 1.5)
    return {"low": low, "high": high}


def _weights(client, name):
    feeds = client.get("/api/feeds/weights").json()["feeds"]
    return next(f["sourceWeight"] for f in feeds if f["name"] == name)


class TestFeedWeightsRead:
    def test_default_weight_is_one_point_zero(self, client):
        feed = create_feed("https://rank.example/default.xml", "Rank Default", "technology")
        assert _weights(client, "Rank Default") == 1.0
        assert feed.id is not None

    def test_reports_stored_weights(self, client, feeds):
        assert _weights(client, feeds["low"].name) == 0.5
        assert _weights(client, feeds["high"].name) == 1.5

    def test_all_presets_round_trip(self, client, feeds):
        """Each UI preset must read back as itself after being saved.

        1.0 is the one that regressed — the frontend rendered it as "1" and
        matched no option — so it is asserted alongside the others.
        """
        feed = feeds["low"]
        for preset in (0.5, 1.0, 1.5, 2.0):
            res = client.patch("/api/feeds/weights", json={"feedId": feed.id, "weight": preset})
            assert res.status_code == 200, res.text
            assert _weights(client, feed.name) == preset


class TestWeightWriteHonesty:
    """§3.1-3.3 — a weight change must be what it claims to be.

    Every case here used to answer `{"success": true}` while persisting
    nothing, which is worse than an error: the UI showed the change as applied
    and the select snapped back with no reason given.
    """

    def test_unknown_feed_is_404_not_success(self, client):
        res = client.patch("/api/feeds/weights", json={"feedId": 99999999, "weight": 1.5})
        assert res.status_code == 404, res.text
        assert "success" not in res.json()

    def test_protected_manual_feed_refuses_a_weight(self, client):
        """§3.3 — Manual Links can't be edited or deleted; its weight is no different."""
        from app.db.repository import MANUAL_FEED_URL, get_all_feeds

        manual = next(f for f in get_all_feeds() if f.url == MANUAL_FEED_URL)
        res = client.patch("/api/feeds/weights", json={"feedId": manual.id, "weight": 2.0})
        assert res.status_code == 403, res.text
        assert _weights(client, manual.name) == 1.0, "the protected feed's weight changed"

    @pytest.mark.parametrize("weight", [0.1, 0.49, 2.01, 10.0, -1.0])
    def test_weight_outside_the_scored_range_is_rejected(self, client, feeds, weight):
        """§3.1 — the API accepted 0.1-10.0 while score_article clamped to
        0.5-2.0, so a stored 4.0 scored identically to 2.0. Anything outside
        the range the scorer actually reads is now refused at the boundary.
        """
        feed = feeds["high"]
        res = client.patch("/api/feeds/weights", json={"feedId": feed.id, "weight": weight})
        assert res.status_code == 422, f"{weight} was accepted: {res.text}"
        assert _weights(client, feed.name) == 1.5, "a rejected weight was stored anyway"

    @pytest.mark.parametrize("weight", [0.5, 0.9, 1.0, 1.7, 2.0])
    def test_weight_inside_the_scored_range_is_stored_exactly(self, client, feeds, weight):
        """The value stored must be the value scored — no hidden rounding."""
        feed = feeds["high"]
        res = client.patch("/api/feeds/weights", json={"feedId": feed.id, "weight": weight})
        assert res.status_code == 200, res.text
        assert _weights(client, feed.name) == weight

    def test_accepted_range_matches_the_range_the_scorer_reads(self):
        """§3.1/§3.5 — one range, three places.

        The API accepted 0.1-10.0 while score_article clamped to 0.5-2.0. Any
        value outside 0.5-2.0 that the API accepts is stored but scored as one
        of the endpoints, which is the lie §3.1 exists to remove.
        """
        from app.lib.ranking import scorer
        from app.schemas import FEED_WEIGHT_MAX, FEED_WEIGHT_MIN

        assert (FEED_WEIGHT_MIN, FEED_WEIGHT_MAX) == (0.5, 2.0)

        # The scorer's own clamp must not be wider than what can be stored.
        source = Path(scorer.__file__).read_text()
        clamp = re.search(
            r"clamped_weight = min\(max\(source_weight, ([\d.]+)\), ([\d.]+)\)", source
        )
        assert clamp, "could not find the scorer's weight clamp"
        assert float(clamp.group(1)) == FEED_WEIGHT_MIN
        assert float(clamp.group(2)) == FEED_WEIGHT_MAX

    def test_the_four_ui_presets_are_all_accepted(self, client, feeds):
        """The presets in src/lib/ranking/weightPresets.ts must be in range.

        A preset outside the accepted range would be rejected by the very
        control that offers it. This pins the numbers; the labels and their
        rendering are frontend-only and have no test harness in this repo.
        """
        feed = feeds["low"]
        for preset in (0.5, 1.0, 1.5, 2.0):
            res = client.patch("/api/feeds/weights", json={"feedId": feed.id, "weight": preset})
            assert res.status_code == 200, f"preset {preset} rejected: {res.text}"

    def test_stored_weight_reaches_the_scorer_unchanged(self, client, feeds):
        """§3.1 end to end: 2.0 and 0.5 must score differently, not both as 2.0."""
        from app.db.repository import get_article_by_id, upsert_article
        from app.lib.ranking.scorer import score_articles_for_category

        feed = feeds["low"]
        article_id = upsert_article(
            feed.id,
            {"guid": "w-range-1", "title": "Reg range probe story", "link": "https://rank.example/wr",
             "published_at": "2020-01-01T00:00:00Z", "content": None},
            "w-range-hash",
        )

        client.patch("/api/feeds/weights", json={"feedId": feed.id, "weight": 0.5})
        score_articles_for_category("technology", [article_id])
        low = get_article_by_id(article_id).relevance_score

        client.patch("/api/feeds/weights", json={"feedId": feed.id, "weight": 2.0})
        score_articles_for_category("technology", [article_id])
        high = get_article_by_id(article_id).relevance_score

        # 0.5 -> 0 of 20 source points; 2.0 -> all 20.
        assert high - low == pytest.approx(20.0)