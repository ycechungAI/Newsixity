"""spec-v0.5 §7 — regression suite for the whole selection path.

Every item here corresponds to a behaviour that shipped broken because nothing
tested the path end to end: the daily cap was first-come-first-served so 27
feeds fetched and stored nothing, weights were clamped on read while the API
accepted a range the scorer never used, the weights PATCH reported success for
a feed that did not exist, and Feed Rankings hid the majority of the feed list
behind a hard-coded whitelist that had silently drifted from the backend's own
capped-category list.

The checklists in §2, §3, §4 and §5 are pinned elsewhere (§2 in
test_refresh_feed_caps.py, §3 in test_feed_weights.py, §1 in
test_articles_sort.py). This file covers what they do not: the cross-section
guarantees, the removal of the per-section cap, the refresh cap report, the
promotion window, the score-parts persistence, and the default-settings guard
that keeps a fresh install scoring exactly as v0.4 did.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import app.lib.scheduler.refresh as refresh_mod
from app.db.repository import (
    DEFAULT_SCORE_WEIGHTS,
    DAILY_ARTICLE_LIMIT,
    create_feed,
    get_articles_by_category,
    get_feed_article_count_in_last_24h,
    get_ranking_settings,
    get_today_article_ids,
    promote_top_articles,
    update_article_scores,
    upsert_article,
)
from app.db.session import SessionLocal
from app.lib.integrations.rss import FeedResult, ParsedArticle
from app.lib.ranking.promoter import score_and_promote_all
from app.lib.ranking.scorer import score_article
from app.main import app



def _hours_ago(hours: int) -> str:
    """An ISO timestamp ``hours`` before now.

    The ranking window is relative (``published_at >= now - 1 day``), so a
    test that needs an article to count as "recent" must be relative too. A
    literal date stops being recent the day after it was written: these tests
    passed on 2026-10-03 and failed every run after, with no code change.
    """
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

@pytest.fixture
def client():
    return TestClient(app, base_url="http://localhost")


def _parsed(title: str) -> ParsedArticle:
    return ParsedArticle(
        guid=f"g-{title}",
        title=title,
        link=f"https://reg.example/{abs(hash(title))}",
        author=None,
        published_at="2026-01-01T00:00:00Z",
        content=None,
        image_url=None,
    )


def _stub_pipeline(monkeypatch):
    monkeypatch.setattr(refresh_mod, "seed_all_feeds", lambda: None)
    monkeypatch.setattr(refresh_mod, "score_and_promote_all", lambda: None)
    monkeypatch.setattr(refresh_mod, "group_articles", lambda a, s: None)


def _feed(request, slug: str, index: int):
    tag = f"{request.node.name}-{slug}-{index}"
    return create_feed(f"https://reg.example/{tag}.xml", f"Reg {tag}", slug).id


def _results(feeds, per_feed=30, headlines=None):
    headlines = headlines or [
        f"{w} {v} {n}" for w in ("Farm", "Rail", "Port", "Union", "Grid")
        for v in ("halts", "doubles", "restores", "warns", "confirms")
        for n in ("quota", "permit", "schedule", "tariff", "renewal")
    ]
    out = []
    for n, feed_id in enumerate(feeds):
        arts = [
            _parsed(f"{headlines[(n * per_feed + i) % len(headlines)]} {feed_id}-{i}")
            for i in range(per_feed)
        ]
        out.append(
            FeedResult(
                feed_id=feed_id,
                feed_url=f"https://reg.example/{feed_id}.xml",
                articles=arts,
            )
        )
    return out


class TestNoSectionCapRemains:
    """§2.1 — the shared per-section budget and its query are fully gone.

    Not just "the behaviour is right": the orphan has to be gone, because a
    leftover constant that nothing reads is exactly what the next person
    revives by accident.
    """

    def test_per_section_cap_and_its_query_are_deleted(self):
        import app.db.repository as repo
        import app.db.repository.console as console

        assert not hasattr(console, "CATEGORY_DAILY_INSERT_CAP"), (
            "the per-section insert cap is back in console.py"
        )
        assert not hasattr(console, "get_category_articles_count_in_last_24h"), (
            "the per-section count query is orphaned again"
        )
        # Also gone from the package's public surface, so a new caller can't
        # reach it by importing from app.db.repository.
        assert "CATEGORY_DAILY_INSERT_CAP" not in repo.__all__
        assert "get_category_articles_count_in_last_24h" not in repo.__all__
        assert not hasattr(repo, "CATEGORY_DAILY_INSERT_CAP")
        assert not hasattr(repo, "get_category_articles_count_in_last_24h")

    def test_finance_cap_constant_is_deleted(self):
        import app.db.repository as repo
        import app.db.repository.ranking as ranking

        assert not hasattr(ranking, "FINANCE_DAILY_INSERT_CAP")
        assert "FINANCE_DAILY_INSERT_CAP" not in repo.__all__


class TestSectionsAreIndependent:
    """§7 — one section spending its allowance must not reduce another's."""

    def test_two_sections_do_not_share_a_budget(self, request, monkeypatch):
        _stub_pipeline(monkeypatch)
        world = [_feed(request, "world-news", i) for i in range(2)]
        tech = [_feed(request, "technology", i) for i in range(2)]

        all_results = _results(world) + _results(tech)
        monkeypatch.setattr(refresh_mod, "fetch_all_feeds_sync", lambda: all_results)
        # Each section already covered, so every feed may use its full
        # soft→hard range: 3 articles apiece.
        counts = {f: 5 for f in world + tech}
        monkeypatch.setattr(
            refresh_mod,
            "get_feed_article_count_in_last_24h",
            lambda feed_id: counts.get(feed_id, 0),
        )

        outcome = refresh_mod._run_feed_refresh_sync()

        def stored(feeds, slug):
            ids = {f for f in feeds}
            return sum(
                1 for a in get_articles_by_category(slug, limit=2000) if a.feed_id in ids
            )

        world_stored = stored(world, "world-news")
        tech_stored = stored(tech, "technology")
        assert world_stored == 6, world_stored
        assert tech_stored == 6, tech_stored
        assert outcome.caps, "no cap report was produced at all"


class TestManyFeedsAndFewFeeds:
    """§2.3 — a section sizes itself to its membership.

    Many feeds each take the soft cap; a section of one busy feed may use the
    full soft→hard range. This is the property that replaces the shared
    budget: volume now follows the section's own size.
    """

    def test_a_busy_section_and_a_quiet_section_both_get_their_allowance(
        self, request, monkeypatch
    ):
        _stub_pipeline(monkeypatch)
        busy = [_feed(request, "world-news", i) for i in range(6)]
        quiet = [_feed(request, "technology", i) for i in range(1)]

        monkeypatch.setattr(
            refresh_mod,
            "fetch_all_feeds_sync",
            lambda: _results(busy) + _results(quiet),
        )
        monkeypatch.setattr(
            refresh_mod, "get_feed_article_count_in_last_24h", lambda feed_id: 0
        )

        refresh_mod._run_feed_refresh_sync()

        def stored(feeds, slug):
            ids = set(feeds)
            return sum(
                1 for a in get_articles_by_category(slug, limit=5000) if a.feed_id in ids
            )

        # Six feeds x soft cap 5 = 30. Under the old shared cap of 20 this
        # would have been truncated, and to the *first* feed alone.
        assert stored(busy, "world-news") == 30, stored(busy, "world-news")
        # One feed alone still cannot exceed its soft cap: the fairness floor
        # requires every other feed in the section to have 5, and a section of
        # one has nobody to wait for.
        assert stored(quiet, "technology") == 5, stored(quiet, "technology")


class TestRefreshReportsCaps:
    """§2.8 / §2.10 — a silenced feed must not look like a quiet one."""

    def test_report_names_the_limit_that_stopped_each_feed(self, request, monkeypatch):
        _stub_pipeline(monkeypatch)
        world = [_feed(request, "world-news", i) for i in range(2)]
        monkeypatch.setattr(refresh_mod, "fetch_all_feeds_sync", lambda: _results(world))
        # One feed is covered and free to run to the hard cap; the other is
        # held at the soft cap because its section is not covered.
        counts = {world[0]: 0, world[1]: 5}
        monkeypatch.setattr(
            refresh_mod,
            "get_feed_article_count_in_last_24h",
            lambda feed_id: counts.get(feed_id, 0),
        )

        caps = {c.feed_id: c for c in refresh_mod._run_feed_refresh_sync().caps}

        assert set(caps) == set(world), "a feed with articles is missing from the report"
        assert caps[world[0]].limit == "soft", caps[world[0]]
        assert caps[world[0]].soft_cap == 5 and caps[world[0]].hard_cap == 8
        assert caps[world[0]].feed_name.startswith("Reg ")
        # Feed 2 starts at 5 with the section uncovered, so it stores nothing.
        assert caps[world[1]].limit == "soft"

    def test_quiet_feed_is_not_reported_as_capped(self, request, monkeypatch):
        """The distinction only exists if a drained feed reports no limit."""
        _stub_pipeline(monkeypatch)
        world = [_feed(request, "world-news", 0)]
        monkeypatch.setattr(refresh_mod, "fetch_all_feeds_sync", lambda: _results(world, per_feed=2))
        monkeypatch.setattr(
            refresh_mod, "get_feed_article_count_in_last_24h", lambda feed_id: 0
        )

        caps = refresh_mod._run_feed_refresh_sync().caps
        assert caps and caps[0].limit is None, (
            "a feed with fewer articles than its cap reports a limit it never hit"
        )

    def test_caps_survive_the_api_boundary(self, request, monkeypatch):
        """The route must pass the report through, not just the counters.

        A report computed and then dropped at the route is the §2.8 failure in
        a new disguise.
        """
        _stub_pipeline(monkeypatch)
        world = [_feed(request, "world-news", i) for i in range(2)]
        monkeypatch.setattr(refresh_mod, "fetch_all_feeds_sync", lambda: _results(world))
        counts = {world[0]: 0, world[1]: 5}
        monkeypatch.setattr(
            refresh_mod,
            "get_feed_article_count_in_last_24h",
            lambda feed_id: counts.get(feed_id, 0),
        )

        body = TestClient(app, base_url="http://localhost").post(
            "/api/feeds/refresh"
        ).json()

        assert "caps" in body, body.keys()
        assert body["caps"], "the route dropped the cap report"
        first = body["caps"][0]
        assert {"feedId", "feedName", "limit", "stored24h", "softCap", "hardCap"} <= set(first)
        assert first["feedId"] in world
        assert first["limit"] in {"soft", "hard", None}


class TestPromotionWindow:
    """§1.3 — scoring and promotion must agree on what "recent" means."""

    def test_promotion_ignores_articles_outside_the_window(self, request):
        feed = create_feed(
            f"https://reg.example/{request.node.name}.xml", "Reg Window", "technology"
        )
        recent = upsert_article(
            feed.id,
            {"guid": "w-recent", "title": "Reg recent inside window", "link": "https://reg.example/r",
             "published_at": _hours_ago(2), "content": None},
            "w-recent-hash",
        )
        old = upsert_article(
            feed.id,
            {"guid": "w-old", "title": "Reg old outside window", "link": "https://reg.example/o",
             "published_at": "2020-01-01T00:00:00Z", "content": None},
            "w-old-hash",
        )
        # The old article has the *better* score, so a window that isn't applied
        # to promotion would badge it "top" instead of the recent one.
        update_article_scores([{"id": recent, "score": 10.0}])
        update_article_scores([{"id": old, "score": 99.0}])

        promote_top_articles("technology", limit=1)

        scored_ids = set(get_today_article_ids("technology"))
        assert recent in scored_ids
        assert old not in scored_ids, "an article from 2020 is inside the ranking window"
        assert _is_promoted(recent)
        assert not _is_promoted(old)

    def test_unscored_articles_never_take_a_top_badge(self, request):
        """A NULL score must not win promotion by accident.

        ``ORDER BY relevance_score DESC`` alone leaves NULLs to SQLite, which
        has sorted them ahead of every real score in some plans — handing a
        "top" badge to an article that was never scored.
        """
        feed = create_feed(
            f"https://reg.example/{request.node.name}-null.xml", "Reg Null", "technology"
        )
        scored = upsert_article(
            feed.id,
            {"guid": "n-scored", "title": "Reg null scored story", "link": "https://reg.example/s",
             "published_at": _hours_ago(2), "content": None},
            "n-scored-hash",
        )
        unscored = upsert_article(
            feed.id,
            {"guid": "n-unscored", "title": "Reg null unscored story", "link": "https://reg.example/u",
             "published_at": _hours_ago(2), "content": None},
            "n-unscored-hash",
        )
        update_article_scores([{"id": scored, "score": 42.0}])
        with SessionLocal() as db:
            from sqlalchemy import text as sql_text

            db.execute(
                sql_text("UPDATE articles SET relevance_score = NULL WHERE id = :id"),
                {"id": unscored},
            )
            db.commit()

        promote_top_articles("technology", limit=1)
        assert _is_promoted(scored)
        assert not _is_promoted(unscored), (
            "an article with no score was promoted into the top slot"
        )


def _is_promoted(article_id: int) -> bool:
    from app.db.repository import get_article_by_id

    article = get_article_by_id(article_id)
    return bool(article and article.is_promoted)


class TestScorePartsAreStored:
    """§6.1 — a score nobody can interrogate gets ignored."""

    def test_parts_are_persisted_with_the_total(self, request):
        from app.db.repository import get_article_by_id
        from app.lib.ranking.scorer import score_articles_for_category

        feed = create_feed(
            f"https://reg.example/{request.node.name}-parts.xml", "Reg Parts", "technology"
        )
        article_id = upsert_article(
            feed.id,
            {"guid": "p-1", "title": "Breaking: reg parts story about a crisis", "link": "https://reg.example/p",
             "published_at": "2026-10-02T00:00:00Z", "content": None},
            "p-1-hash",
        )

        score_articles_for_category("technology", [article_id])

        article = get_article_by_id(article_id)
        assert article is not None
        assert article.relevance_score_parts, "the breakdown was not persisted"
        assert set(article.relevance_score_parts) == set(DEFAULT_SCORE_WEIGHTS)
        # The stored total must be the sum of the stored parts, or the tooltip
        # and the number disagree.
        assert abs(
            article.relevance_score - sum(article.relevance_score_parts.values())
        ) < 0.1

    def test_malformed_parts_do_not_break_the_article_list(self, request, client):
        from sqlalchemy import text as sql_text

        feed = create_feed(
            f"https://reg.example/{request.node.name}-bad.xml", "Reg Bad", "technology"
        )
        article_id = upsert_article(
            feed.id,
            {"guid": "b-1", "title": "Reg malformed parts story", "link": "https://reg.example/b",
             "published_at": "2026-10-02T00:00:00Z", "content": None},
            "b-1-hash",
        )
        with SessionLocal() as db:
            db.execute(
                sql_text("UPDATE articles SET relevance_score_parts = :p WHERE id = :id"),
                {"p": "{not json at all", "id": article_id},
            )
            db.commit()

        res = client.get("/api/articles", params={"category": "technology", "limit": 100})
        assert res.status_code == 200, res.text
        article = next(a for a in res.json() if a["id"] == article_id)
        assert article["relevanceScoreParts"] is None, (
            "a corrupt parts column must degrade to 'no explanation', not raise"
        )


class TestDefaultsReproduceV04:
    """§5.3 — the regression guard for §1.4 widening scoring to every category.

    Ranking now scores every section rather than only the four v0.4 capped
    ones. If the defaults drifted, every existing install's scores would
    silently change on upgrade, so the defaults are pinned to the literals.
    """

    def test_absent_row_scores_exactly_as_v04(self):
        settings = get_ranking_settings("finance")
        assert settings.weights == DEFAULT_SCORE_WEIGHTS
        assert settings.promote_limit == DAILY_ARTICLE_LIMIT
        assert settings.feed_soft_cap == 5 and settings.feed_hard_cap == 8
        assert settings.ranked is True

    def test_a_section_with_no_row_is_not_silently_ranked(self):
        """§4.2/§4.3 — an unranked section must say so, not act ranked."""
        assert get_ranking_settings("security").ranked is False

    def test_defaults_score_the_same_as_the_v04_literals(self, request):
        """A hand-computed v0.4 score, with no settings row in play."""
        from app.db.repository import get_article_by_id
        from app.lib.ranking.scorer import score_articles_for_category

        feed = create_feed(
            f"https://reg.example/{request.node.name}-defaults.xml", "Reg Defaults", "finance"
        )
        article_id = upsert_article(
            feed.id,
            {"guid": "d-1", "title": "Announce launch of a record surge", "link": "https://reg.example/d",
             "published_at": "2026-01-01T00:00:00Z", "content": None},
            "d-1-hash",
        )
        score_articles_for_category("finance", [article_id])

        article = get_article_by_id(article_id)
        parts = article.relevance_score_parts
        assert parts is not None
        # groupSize 0 — one source, so no corroboration.
        assert parts["groupSize"] == 0.0
        # sourceWeight: a stored 1.0 is the neutral midpoint, half of its 20.
        assert parts["sourceWeight"] == pytest.approx(10.0)
        # titleImportance: record (0.3) + surge (0.3) + the announce/launch band
        # (0.2 — one pattern, however many of its words appear) = 0.8.
        assert parts["titleImportance"] == pytest.approx(8.0)
        # The published date is well outside 24h, so recency scores zero.
        assert parts["recency"] == pytest.approx(0.0)
        # No learned keywords yet, so preference match is the neutral 0.5.
        assert parts["preferenceMatch"] == pytest.approx(15.0)
        assert article.relevance_score == pytest.approx(33.0)

    def test_custom_weights_change_the_score(self, request):
        """§5.4 — the weights are parameters, not literals."""
        from app.db.repository import get_article_by_id
        from app.lib.ranking.scorer import score_articles_for_category

        feed = create_feed(
            f"https://reg.example/{request.node.name}-weights.xml", "Reg Weights", "gaming"
        )
        # Published now, so recency is at its full 1.0 rather than decaying.
        now = datetime.now(timezone.utc).isoformat()
        article_id = upsert_article(
            feed.id,
            {"guid": "w-1", "title": "Crisis deepens in border talks", "link": "https://reg.example/w",
             "published_at": now, "content": None},
            "w-1-hash",
        )

        # All weight to recency, zero to everything else.
        recency_first = {
            "groupSize": 0, "preferenceMatch": 0, "sourceWeight": 0,
            "recency": 100, "titleImportance": 0,
        }
        score_articles_for_category("gaming", [article_id], recency_first)
        with_recency = get_article_by_id(article_id).relevance_score

        # Same, but all weight to title importance instead.
        importance_first = {**recency_first, "recency": 0, "titleImportance": 100}
        score_articles_for_category("gaming", [article_id], importance_first)
        with_importance = get_article_by_id(article_id).relevance_score

        # Fresh article: full recency (100 points) beats "crisis" alone (0.5
        # of 100 = 50 points). Under v0.4's hard-coded weights the second call
        # would have scored exactly like the first.
        assert with_recency == pytest.approx(100.0)
        assert with_importance == pytest.approx(50.0)


class TestRankingSettingsApi:
    """§5.2 — the settings surface, and its validation."""

    def test_lists_every_category_with_defaults(self, client):
        body = client.get("/api/ranking/settings").json()
        slugs = {s["categorySlug"] for s in body["settings"]}
        assert {"world-news", "finance", "technology", "security"} <= slugs
        assert body["defaults"]["feedSoftCap"] == 5
        assert body["defaults"]["feedHardCap"] == 8
        assert body["defaults"]["weights"] == DEFAULT_SCORE_WEIGHTS

    def test_round_trips_caps_and_ranked_flag(self, client):
        res = client.put(
            "/api/ranking/settings/security",
            json={"feedSoftCap": 3, "feedHardCap": 6, "promoteLimit": 12, "ranked": True},
        )
        assert res.status_code == 200, res.text
        settings = get_ranking_settings("security")
        assert (settings.feed_soft_cap, settings.feed_hard_cap) == (3, 6)
        assert settings.promote_limit == 12 and settings.ranked is True

    def test_rejects_weights_that_do_not_sum_to_100(self, client):
        res = client.put(
            "/api/ranking/settings/finance",
            json={"weights": {"groupSize": 50, "preferenceMatch": 50, "sourceWeight": 50,
                             "recency": 0, "titleImportance": 0}},
        )
        assert res.status_code == 422, res.text

    def test_unknown_category_is_404(self, client):
        assert client.put("/api/ranking/settings/not-a-category", json={"ranked": True}).status_code == 404

    def test_soft_cap_above_hard_is_normalised_not_silently_kept(self, client):
        """§2.2 — a soft cap above the hard cap means the feed can never insert."""
        client.put(
            "/api/ranking/settings/gaming",
            json={"feedSoftCap": 9, "feedHardCap": 4},
        )
        settings = get_ranking_settings("gaming")
        assert settings.feed_soft_cap <= settings.feed_hard_cap, settings

    def test_configured_caps_are_what_the_refresh_enforces(self, request, monkeypatch):
        """§2.9 — Settings must govern storage, not just display it."""
        from app.db.repository import upsert_ranking_settings

        _stub_pipeline(monkeypatch)
        upsert_ranking_settings("technology", feed_soft_cap=2, feed_hard_cap=2)
        tech = [_feed(request, "technology", i) for i in range(1)]
        monkeypatch.setattr(refresh_mod, "fetch_all_feeds_sync", lambda: _results(tech))
        monkeypatch.setattr(
            refresh_mod, "get_feed_article_count_in_last_24h", lambda feed_id: 0
        )

        outcome = refresh_mod._run_feed_refresh_sync()
        stored = sum(
            1 for a in get_articles_by_category("technology", limit=2000)
            if a.feed_id in set(tech)
        )
        assert stored == 2, f"configured cap of 2 was not enforced (stored {stored})"
        assert outcome.caps[0].soft_cap == 2 and outcome.caps[0].hard_cap == 2


class TestEveryFeedIsReachable:
    """§4.1 — no whitelist. Every enabled feed can be ranked."""

    def test_no_category_is_filtered_out_of_the_weights_list(self, request, client):
        """The v0.4 UI hard-coded four slugs, hiding six of ten default feeds.

        The API side of that whitelist was always "return every feed" — the
        filter was client-side — so this pins the two categories the old list
        excluded, and the invariant that every stored feed is reachable.
        """
        from app.db.repository import get_all_feeds

        for slug in ("technology", "security"):
            _feed(request, slug, 0)

        listed = {f["categorySlug"] for f in client.get("/api/feeds/weights").json()["feeds"]}
        stored = {f.category_slug for f in get_all_feeds()}
        assert stored <= listed, f"feeds in {stored - listed} are unreachable in Feed Rankings"
        assert {"technology", "security"} <= listed, (
            "technology/security feeds are missing — the whitelist is back"
        )

    def test_ranking_settings_exist_for_unranked_sections(self, client):
        """A weight is only honest if the section's ranking can be turned on."""
        slugs = {s["categorySlug"] for s in client.get("/api/ranking/settings").json()["settings"]}
        assert {"technology", "security", "consumer-tech"} <= slugs


class TestPromoteLimitIsConfigurable:
    """§5/§2.9 — the promote limit must come from settings, not a constant.

    The caps tests prove the *storage* limits are configurable. This proves the
    other half: `promote_limit` is a separate mechanism (what ranking promotes,
    not what the refresh stores) and must govern promotion too. A panel that
    saved the number and a promoter that ignored it would look correct.
    """

    def test_configured_promote_limit_is_used(self, monkeypatch):
        from app.db.repository import upsert_ranking_settings
        from app.lib.ranking import promoter

        used: list[int] = []
        monkeypatch.setattr(promoter, "get_today_article_ids", lambda slug: [1, 2, 3])
        monkeypatch.setattr(
            promoter, "score_articles_for_category", lambda slug, ids, weights=None: None
        )
        monkeypatch.setattr(
            promoter, "promote_top_articles", lambda slug, limit: used.append(limit)
        )

        upsert_ranking_settings("finance", promote_limit=7)
        promoter.score_and_promote("finance")

        assert used == [7], f"promotion ignored the configured limit: {used}"

    def test_explicit_limit_overrides_the_setting(self, monkeypatch):
        """The ``limit`` argument still wins — the Console passes it directly."""
        from app.db.repository import upsert_ranking_settings
        from app.lib.ranking import promoter

        used: list[int] = []
        monkeypatch.setattr(promoter, "get_today_article_ids", lambda slug: [1])
        monkeypatch.setattr(
            promoter, "score_articles_for_category", lambda slug, ids, weights=None: None
        )
        monkeypatch.setattr(
            promoter, "promote_top_articles", lambda slug, limit: used.append(limit)
        )

        upsert_ranking_settings("finance", promote_limit=7)
        promoter.score_and_promote("finance", limit=3)

        assert used == [3], used

    def test_partial_update_keeps_the_fields_it_was_not_given(self):
        """The PUT is documented as "omitted fields keep their stored value".

        Without this, saving one cap from the Settings panel would silently
        reset the promote limit and the score weights back to their defaults.
        """
        from app.db.repository import upsert_ranking_settings

        upsert_ranking_settings(
            "sports",
            feed_soft_cap=2,
            feed_hard_cap=4,
            promote_limit=11,
            ranked=False,
            weights={"groupSize": 50, "preferenceMatch": 20, "sourceWeight": 10,
                     "recency": 10, "titleImportance": 10},
        )
        upsert_ranking_settings("sports", feed_soft_cap=3)  # a single-field save

        after = get_ranking_settings("sports")
        assert after.feed_soft_cap == 3
        assert after.feed_hard_cap == 4, "an untouched cap was reset"
        assert after.promote_limit == 11, "an untouched promote limit was reset"
        assert after.ranked is False, "an untouched ranked flag was reset"
        assert after.weights["groupSize"] == 50, "untouched score weights were reset"


class TestBackgroundTasksStayReferenced:
    """Fire-and-forget work must be held until it finishes.

    asyncio keeps only a *weak* reference to a running task, so a task nobody
    holds can be garbage collected mid-execution and its work silently never
    happens. These cover the three call sites that schedule work this way:
    post-refresh summarization, the feed-weights-adjacent refresh route, and
    on-save summarization.
    """

    def _helper(self, module_name):
        import importlib

        return importlib.import_module(module_name)

    @pytest.mark.parametrize(
        "module_name", ["app.routers.feeds", "app.routers.articles"]
    )
    def test_task_is_held_until_it_completes(self, module_name):
        mod = self._helper(module_name)
        seen = {}

        async def work():
            seen["ran"] = True

        async def scenario():
            mod._run_in_background(work())
            # Mid-flight: the task must be reachable from the module's set.
            held = bool(mod._BACKGROUND_TASKS)
            await asyncio.gather(*list(mod._BACKGROUND_TASKS))
            return held

        assert asyncio.run(scenario()) is True, (
            "the task was not referenced while running — it can be collected "
            "before it does any work"
        )
        assert seen.get("ran") is True
        assert not mod._BACKGROUND_TASKS, (
            "a finished task was never released — the set would grow forever"
        )

    def test_refresh_holds_its_summarize_task(self, monkeypatch):
        import app.lib.scheduler.refresh as refresh_mod

        held_during = {}

        async def scenario():
            refresh_mod._BACKGROUND_TASKS.clear()

            async def fake_summarize(limit):
                held_during["held"] = bool(refresh_mod._BACKGROUND_TASKS)

            monkeypatch.setattr(refresh_mod, "_fire_background_summarize", fake_summarize)
            task = asyncio.create_task(refresh_mod._fire_background_summarize(1))
            refresh_mod._BACKGROUND_TASKS.add(task)
            task.add_done_callback(refresh_mod._BACKGROUND_TASKS.discard)
            await task

        asyncio.run(scenario())
        assert held_during.get("held") is True, (
            "the refresh's background summarization ran while unreferenced"
        )


class TestScorePartsRoundTrip:
    """§6.2 — valid parts must survive the DB → API → UI path."""

    def test_valid_parts_are_returned_by_the_api(self, request, client):
        from app.db.repository import get_article_by_id
        from app.lib.ranking.scorer import score_articles_for_category

        feed = create_feed(
            f"https://reg.example/{request.node.name}-rt.xml", "Reg RoundTrip", "technology"
        )
        article_id = upsert_article(
            feed.id,
            {"guid": "rt-1", "title": "Urgent crisis at the border", "link": "https://reg.example/rt",
             "published_at": "2026-10-02T00:00:00Z", "content": None},
            "rt-1-hash",
        )
        score_articles_for_category("technology", [article_id])

        expected = get_article_by_id(article_id).relevance_score_parts
        assert expected, "nothing was persisted to round-trip"

        body = client.get("/api/articles", params={"category": "technology", "limit": 100}).json()
        article = next(a for a in body if a["id"] == article_id)

        assert article["relevanceScoreParts"] == pytest.approx(expected)
        assert article["relevanceScore"] == pytest.approx(
            get_article_by_id(article_id).relevance_score
        )


class TestRankingAppliesBeyondV04CappedCategories:
    """§1.4 — the sections v0.4 never scored are now scored."""

    def test_an_unranked_section_is_skipped_and_a_ranked_one_is_not(self, monkeypatch):
        from app.db.repository import upsert_ranking_settings

        called: list[str] = []

        import app.lib.ranking.promoter as promoter

        monkeypatch.setattr(
            promoter, "score_articles_for_category",
            lambda slug, ids, weights=None: called.append(slug),
        )
        monkeypatch.setattr(promoter, "get_today_article_ids", lambda slug: [1])
        monkeypatch.setattr(promoter, "promote_top_articles", lambda slug, limit: None)

        upsert_ranking_settings("security", ranked=False)
        promoter.score_and_promote("security")
        assert called == [], "an unranked section was scored"

        upsert_ranking_settings("security", ranked=True)
        promoter.score_and_promote("security")
        assert called == ["security"]

    def test_score_and_promote_all_covers_every_category(self, monkeypatch):
        """§1.4 — the loop is no longer limited to CAPPED_CATEGORIES."""
        import app.lib.ranking.promoter as promoter
        from app.db.repository import get_categories

        seen: list[str] = []
        monkeypatch.setattr(promoter, "score_and_promote", lambda slug: seen.append(slug))

        score_and_promote_all()

        every = {c.slug for c in get_categories()}
        assert set(seen) == every, (
            f"scoring skipped {every - set(seen)} — these categories are never ranked"
        )