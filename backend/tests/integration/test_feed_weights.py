"""GET /api/feeds/weights — the Settings > Feed Rankings read path.

Every feed starts at source_weight 1.0. That value is the case the frontend
got wrong: React matches <select> values as strings, and String(1.0) is "1"
while the option's value is "1.0", so a feed at the default weight matched no
option and the browser displayed the first one (Low). These tests pin the
weight each feed actually reports, so the preset the UI shows is the preset
that was saved.
"""

from __future__ import annotations

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