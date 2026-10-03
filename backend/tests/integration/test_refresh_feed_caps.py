"""Per-feed daily caps with a section-wide fairness floor (spec-v0.5 §2).

Replaces the per-section insert cap. Today `CATEGORY_DAILY_INSERT_CAP = 20` is
shared across a category and the first feed processed drains it, so the others
are silently skipped for the rest of the 24h window - measured live: technology
gave 64 of 80 articles to Ars Technica and 0 to five other feeds; sports gave
all 80 to BBC Sport; world-news gave all 80 to Al Jazeera.

§2 removes the per-section cap and bounds each feed instead:

| Limit    | Value | Meaning                                       |
|----------|-------|-----------------------------------------------|
| Soft cap | 5     | Free up to 5 articles in a rolling 24h window |
| Hard cap | 8     | Absolute ceiling, never exceeded              |

and adds the fairness floor: a feed's 6th article is only permitted once every
other feed in its section already has 5.
"""

from __future__ import annotations

import pytest

import app.lib.scheduler.refresh as refresh_mod
from app.db.repository import create_feed, get_articles_by_category
from app.lib.integrations.rss import FeedResult, ParsedArticle
from app.lib.scheduler.refresh import FEED_DAILY_HARD_CAP, FEED_DAILY_SOFT_CAP

# Distinct headlines. The fuzzy dedup is real, so titles have to genuinely
# differ - "feed 1 article 0" vs "feed 2 article 1" is near-identical and gets
# (correctly) rejected as one story.
# 96 headlines, verified pairwise non-duplicate by is_duplicate at
# generation time. Templated titles like "feed 2 article 0" do NOT work here:
# the fuzzy dedup reads them as one story (5 of 6 tokens shared), so every
# feed after the first had its whole entry list rejected and inserted nothing.
_HEADLINES = [
    "Farming halts grants", "Chipmaker doubles grants", "Ferry expands quotas",
    "Housing halts capacity", "Library delays inspections", "Wildfire revises schedules",
    "Health cuts tariffs", "Ferry restores zones", "School doubles tariffs",
    "Rail expands inspections", "Housing patches tariffs", "Hospital approves permits",
    "Clinic cancels zones", "Coastal revises renewals", "Rail cuts rates",
    "Pension warns funding", "School patches quotas", "Wildfire approves quotas",
    "Fishing approves renewals", "Ferry reopens permits", "Clinic cuts inspections",
    "Fishing confirms rates", "Forest revises timetables", "Library delays schedules",
    "Chipmaker delays funding", "Port reports timetables", "Hospital revises capacity",
    "Union revises funding", "Bakery revises quotas", "Wildfire confirms renewals",
    "Canal patches permits", "Health cuts coverage", "Union restores quotas",
    "Pension suspends grants", "Rail records grants", "Health reports inspections",
    "School revises grants", "Health reports renewals", "Grid confirms contracts",
    "Clinic halts coverage", "Border cancels renewals", "Bridge reopens schedules",
    "Hospital doubles grants", "Energy confirms schedules", "Chipmaker warns transfers",
    "Recycling approves quotas", "Airport delays coverage", "Pension approves grants",
    "Border patches transfers", "Library expands timetables", "Coastal reopens zones",
    "Grid records capacity", "Orchard approves capacity", "Wildfire restores zones",
    "Library delays quotas", "Book reopens capacity", "Forest approves tariffs",
    "Shipping cancels grants", "Union revises inspections", "Museum reopens inspections",
    "Quarry restores funding", "Canal seeks grants", "Housing reports rates",
    "Forest seeks quotas", "School halts transfers", "Housing halts permits",
    "Tunnel halts renewals", "Grid approves schedules", "Border suspends quotas",
    "Bakery approves rates", "Bakery suspends funding", "Forest revises capacity",
    "Bridge suspends zones", "Energy doubles timetables", "Ferry expands funding",
    "Coastal restores grants", "Bakery revises transfers", "Chipmaker cancels inspections",
    "Book doubles zones", "Recycling expands zones", "Quarry doubles inspections",
    "Farming revises zones", "Fishing cancels coverage", "Mint approves inspections",
    "Union confirms zones", "Forest seeks inspections", "Border doubles renewals",
    "School halts inspections", "Hospital cancels timetables", "Union records coverage",
    "Forest reports contracts", "Housing patches renewals", "Farming doubles permits",
    "Recycling records transfers", "Rail confirms quotas", "Hospital cancels renewals",
]


def _parsed(title: str) -> ParsedArticle:
    """A real ParsedArticle - the pipeline calls dataclasses.asdict() on it."""
    return ParsedArticle(
        guid=f"guid-{title}",
        title=title,
        link=f"https://cap.example/{abs(hash(title))}",
        author=None,
        published_at="2026-01-01T00:00:00Z",
        content=None,
        image_url=None,
    )


@pytest.fixture
def world(monkeypatch, request):
    """``n`` world-news feeds in the session's throwaway database."""
    tag = request.node.name
    monkeypatch.setattr(refresh_mod, "seed_all_feeds", lambda: None)
    monkeypatch.setattr(refresh_mod, "score_and_promote_all", lambda: None)
    monkeypatch.setattr(refresh_mod, "group_articles", lambda a, s: None)
    return [
        create_feed(
            f"https://cap.example/{tag}/{i}.xml", f"Cap Feed {i} {tag}", "world-news"
        ).id
        for i in range(4)
    ]


def _results(feeds, per_feed=20):
    """One FeedResult per feed, each drawing on a disjoint pool of headlines.

    Two traps here, both learned the hard way:

    - Titles must be genuinely unrelated, not templated. is_duplicate treats
      "f2-0-headline number 0 about topic" and "f3-0-headline number 0 about
      topic" as the *same story* - they share 5 of 6 tokens - so every feed but
      the first had all 20 entries rejected and inserted nothing.
    - Headlines must not be reused across tests. The session database is
      shared, so a title already stored by an earlier test is a dedup hit.
    """
    out = []
    for n, feed_id in enumerate(feeds):
        articles = []
        for i in range(per_feed):
            index = (n * per_feed + i) % len(_HEADLINES)
            headline = _HEADLINES[(index + _offset_for(feed_id)) % len(_HEADLINES)]
            articles.append(_parsed(f"{headline} ({feed_id}-{i})"))
        out.append(
            FeedResult(
                feed_id=feed_id,
                feed_url=f"https://cap.example/{feed_id}.xml",
                articles=articles,
            )
        )
    return out


def _offset_for(feed_id: int) -> int:
    """Rotate each feed's window so no two feeds draw the same headline."""
    return (feed_id * 11) % len(_HEADLINES)


def _run(monkeypatch, feeds, per_feed=20, **overrides):
    """Drive the refresh over synthetic results against the real database.

    Only the network fetch and the counts are stubbed - dedup, category lookup
    and insert all run for real.
    """
    monkeypatch.setattr(refresh_mod, "fetch_all_feeds_sync", lambda: _results(feeds, per_feed))
    counts = overrides.get("counts") or {}
    monkeypatch.setattr(
        refresh_mod,
        "get_feed_article_count_in_last_24h",
        lambda feed_id: counts.get(feed_id, 0),
    )
    return refresh_mod._run_feed_refresh_sync()


def _per_feed_counts(feeds, prefix_free_titles=None):
    """Articles stored per feed id in world-news."""
    out = {f: 0 for f in feeds}
    for article in get_articles_by_category("world-news", limit=2000):
        if prefix_free_titles and article.title not in prefix_free_titles:
            continue
        if article.feed_id in out:
            out[article.feed_id] += 1
    return out


class TestQualityCut:
    """§2 currently stores whatever arrives first in each feed's XML. When a
    feed lists five filler headlines before its breaking ones, all five slots
    go to filler and the high-impact stories never land. The cut should rank
    candidates by importance + preference match + source weight within each
    feed's turn."""

    def test_quality_beats_xml_order_within_a_feed(self, world, monkeypatch):
        import app.lib.scheduler.refresh as refresh_mod

        # One feed, so the soft cap is the only governor: exactly 5 stored.
        filler = [
            "Local council publishes agenda",
            "Library timetable updated for autumn",
            "Council confirms parking rates",
            "Weather outlook for the weekend",
            "Volunteer group meets Tuesday",
        ]
        # The strong ones sit later in the feed's XML list.
        strong = [
            "Breaking: wildfire forces evacuations near coast",
            "Urgent: hospital network hit by outage",
            "Crisis deepens in border talks",
            "Record surge in market volatility",
            "Historic treaty signed at summit",
        ]

        def one_feed():
            feed_id = world[0]
            arts = [_parsed(t) for t in filler] + [_parsed(t) for t in strong]
            return [
                FeedResult(
                    feed_id=feed_id,
                    feed_url=f"https://cap.example/{feed_id}.xml",
                    articles=arts,
                )
            ]

        monkeypatch.setattr(refresh_mod, "fetch_all_feeds_sync", lambda: one_feed())
        monkeypatch.setattr(
            refresh_mod, "get_feed_article_count_in_last_24h", lambda feed_id: 0
        )

        refresh_mod._run_feed_refresh_sync()

        stored_titles = {a.title for a in get_articles_by_category("world-news", limit=200)}
        assert stored_titles, "nothing was stored"
        overlap = {t for t in strong if t in stored_titles}
        assert len(overlap) >= 3, (
            f"quality cut lost to XML order: stored {len(stored_titles)} but only "
            f"{len(overlap)} of the strong headlines made it"
        )


class TestHardCap:
    def test_no_feed_exceeds_hard_cap(self, world, monkeypatch):
        """§2.2 - 8 is absolute, however busy the feed is."""
        _run(monkeypatch, world, per_feed=30)

        counts = _per_feed_counts(world)
        assert counts, "nothing was stored at all"
        assert max(counts.values()) <= 8, f"hard cap exceeded: {counts}"

    def test_hard_cap_applies_to_one_very_busy_feed(self, world, monkeypatch):
        """A single feed with 30 articles still cannot take them all."""
        results = [FeedResult(
            feed_id=world[0],
            feed_url="busy",
            articles=[_parsed(f"f{world[0]}-busy-{i}-{_HEADLINES[i % len(_HEADLINES)]}") for i in range(30)],
        )]
        monkeypatch.setattr(refresh_mod, "fetch_all_feeds_sync", lambda: results)
        monkeypatch.setattr(
            refresh_mod, "get_feed_article_count_in_last_24h", lambda feed_id: 0
        )

        _refreshed, new_articles, _errors = refresh_mod._run_feed_refresh_sync()
        assert new_articles <= 8


class TestFairnessFloor:
    def test_sixth_article_requires_every_feed_to_have_five(self, world, monkeypatch):
        """§2.3 - no feed gets a 6th until the whole section is covered.

        Two feeds start with 4 stored and two with 0, so the section is not
        covered. Every feed must stop at 5: the two at 4 take a single article
        to reach the soft cap, the two at 0 climb up to it.
        """
        counts = {world[0]: 4, world[1]: 4, world[2]: 0, world[3]: 0}
        _run(monkeypatch, world, per_feed=30, counts=counts)

        # The stubbed start counts are not reflected in the database, so what
        # lands there is exactly what was inserted this run: the two feeds
        # starting at 4 take one article to reach the soft cap and stop; the
        # two starting at 0 climb up to it and stop. Nobody reaches 6.
        per_feed = _per_feed_counts(world)
        assert per_feed == {
            world[0]: 1,
            world[1]: 1,
            world[2]: FEED_DAILY_SOFT_CAP,
            world[3]: FEED_DAILY_SOFT_CAP,
        }, f"a feed went past the soft cap before the section was covered: {per_feed}"

    def test_sixth_is_allowed_once_section_is_covered(self, world, monkeypatch):
        """With every feed already at 5, a feed may go on to the hard cap."""
        counts = {f: 5 for f in world}
        _run(monkeypatch, world, per_feed=30, counts=counts)

        # Section already covered, so each feed may go from 5 to the hard cap
        # of 8: three articles apiece.
        per_feed = _per_feed_counts(world)
        assert all(v == FEED_DAILY_HARD_CAP - FEED_DAILY_SOFT_CAP for v in per_feed.values()), (
            f"feeds stuck at the soft cap even though the section was covered: {per_feed}"
        )
        assert max(per_feed.values()) <= FEED_DAILY_HARD_CAP

    def test_a_single_lagging_feed_holds_everyone_at_five(self, world, monkeypatch):
        """One quiet feed must not be starved *or* let others run past 5."""
        counts = {world[0]: 5, world[1]: 5, world[2]: 5, world[3]: 0}
        _run(monkeypatch, world, per_feed=30, counts=counts)

        per_feed = _per_feed_counts(world)
        # The three covered feeds must not exceed 5 (+1 to reach the floor);
        # the lagging one must still be free to insert.
        assert all(v <= 6 for v in per_feed.values()), per_feed

    def test_feeds_below_soft_cap_are_always_free(self, world, monkeypatch):
        """A feed with 0 stored is never blocked, even if the section is covered."""
        counts = {world[0]: 8, world[1]: 8, world[2]: 8, world[3]: 0}
        _run(monkeypatch, world, per_feed=30, counts=counts)

        per_feed = _per_feed_counts(world)
        assert per_feed[world[3]] > 0, "a lagging feed was blocked by the hard cap"


class TestDuplicatesDoNotCostAllowance:
    def test_duplicates_do_not_consume_the_allowance(self, world, monkeypatch):
        """§2.6 - a feed republishing old stories must not starve itself.

        The first six entries repeat the same title, so a naive implementation
        would burn its whole budget on duplicates and store nothing.
        """
        results = []
        for n, feed_id in enumerate(world):
            # Six repeats of one title, then six distinct stories. The repeats
            # must not eat the feed's allowance.
            titles = [f"f{feed_id}-dup"] * 6 + [
                f"f{feed_id}-{i}-{_HEADLINES[(i + 7) % len(_HEADLINES)]}" for i in range(6)
            ]
            results.append(FeedResult(
                feed_id=feed_id,
                feed_url=f"https://cap.example/{feed_id}.xml",
                articles=[_parsed(t) for t in titles],
            ))
        monkeypatch.setattr(refresh_mod, "fetch_all_feeds_sync", lambda: results)
        monkeypatch.setattr(
            refresh_mod, "get_feed_article_count_in_last_24h", lambda feed_id: 0
        )

        _refreshed, new_articles, _errors = refresh_mod._run_feed_refresh_sync()
        per_feed = _per_feed_counts(world)

        assert all(v > 0 for v in per_feed.values()), (
            f"a feed lost its whole allowance to duplicates: {per_feed}"
        )
        assert max(per_feed.values()) <= 8


class TestNoSectionCap:
    def test_many_feeds_exceed_the_old_section_cap(self, world, monkeypatch):
        """§2.1 - the shared per-section budget is gone.

        Four feeds at 8 each is 32, above the old CATEGORY_DAILY_INSERT_CAP of
        20. If that cap still applied this would stop at 20.
        """
        counts = {f: 8 for f in world}  # already at the hard cap
        _run(monkeypatch, world, per_feed=30, counts=counts)
        assert all(v == 0 for v in _per_feed_counts(world).values())

        # And a fresh window is free to exceed 20 in total.
        _run(monkeypatch, world, per_feed=30, counts={f: 0 for f in world})
        total = sum(_per_feed_counts(world).values())
        assert total > 0