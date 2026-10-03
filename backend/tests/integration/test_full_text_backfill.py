"""Full-text acquisition shared by both summarize paths, plus the backfill.

The bug these pin: fetching the original page used to live inside the
scheduled summarizer only. Two consequences, both observed on the real install.

1. The on-demand /api/summarize path never fetched, so an article reached via
   the button summarized from a teaser while the same article in the queue
   summarized from full text.
2. The queue only visits *unsummarized* articles, so everything already
   summarized kept its teaser forever — 622 of 712 articles here. BBC Sport
   averaged 145 stored characters while every newer feed averaged 1300-4700,
   purely because BBC's articles were fetched before scraping existed.
"""

from __future__ import annotations

import asyncio

import pytest

# No NEWSIXITY_DB_PATH juggling here: tests/conftest.py already points every
# run at a throwaway database before app.db.session is imported. Setting it
# again at module scope leaked into subprocess-based tests, which then found a
# database with no schema ("no such table: settings").
from app.db.init_db import init_db  # noqa: E402
from app.db.repository import (  # noqa: E402
    create_feed,
    get_article_by_id,
    get_articles_needing_full_text,
    update_article_content,
    update_article_summary,
    upsert_article,
)
from app.lib.dedup.similarity import hash_title  # noqa: E402
from app.lib.services import article_text as at  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _db():
    init_db()
    yield


@pytest.fixture
def feed_id():
    import time
    return create_feed(f"https://ft.test/{time.time()}.xml", "FT Test", "technology").id


def _insert(feed_id, title, content, link="https://example.test/a", saved=0):
    return upsert_article(
        feed_id,
        {
            "guid": f"g-{title}",
            "title": title,
            "link": link,
            "author": None,
            "published_at": "2026-01-01T00:00:00Z",
            "content": content,
            "image_url": None,
        },
        hash_title(title),
    )


class TestNeedsFullText:
    def test_short_text_needs_a_fetch(self):
        assert at.needs_full_text(None)
        assert at.needs_full_text("")
        assert at.needs_full_text("A teaser.")

    def test_full_text_does_not(self):
        assert not at.needs_full_text("word " * 500)  # 2500 chars > threshold


class TestEnsureArticleText:
    def test_replaces_a_teaser(self, feed_id, monkeypatch):
        article_id = _insert(feed_id, "teaser one", "just a teaser")
        art = get_article_by_id(article_id)

        async def fake(url):
            return "Real body text. " * 200

        monkeypatch.setattr(at, "fetch_article_content", fake)
        out = asyncio.run(at.ensure_article_text(art))

        assert len(out) > at.TEASER_MAX_LENGTH
        assert len(get_article_by_id(article_id).content) > at.TEASER_MAX_LENGTH

    def test_leaves_full_text_alone(self, feed_id, monkeypatch):
        article_id = _insert(feed_id, "full one", "Already complete. " * 200)
        art = get_article_by_id(article_id)
        stored_len = len(art.content)  # strip_html trims on insert

        async def must_not_run(url):
            raise AssertionError("re-fetched an article that already has full text")

        monkeypatch.setattr(at, "fetch_article_content", must_not_run)
        out = asyncio.run(at.ensure_article_text(art))

        assert len(out) == stored_len
        assert out == art.content

    def test_a_failed_fetch_keeps_existing_text(self, feed_id, monkeypatch):
        article_id = _insert(feed_id, "fetch fails", "keep this teaser")
        art = get_article_by_id(article_id)

        async def boom(url):
            raise RuntimeError("network down")

        monkeypatch.setattr(at, "fetch_article_content", boom)
        out = asyncio.run(at.ensure_article_text(art))

        assert out == "keep this teaser"
        assert get_article_by_id(article_id).content == "keep this teaser"

    def test_a_short_scrape_does_not_overwrite(self, feed_id, monkeypatch):
        """A worse result must never replace what we have."""
        article_id = _insert(feed_id, "short scrape", "A perfectly good 1200 char teaser")
        art = get_article_by_id(article_id)
        original = art.content

        async def returns_junk(url):
            return "tiny"

        monkeypatch.setattr(at, "fetch_article_content", returns_junk)
        out = asyncio.run(at.ensure_article_text(art))

        assert out == original
        assert get_article_by_id(article_id).content == original

    def test_a_materially_better_short_scrape_is_kept(self, feed_id, monkeypatch):
        """The regression, end to end: a short post improves and stays improved."""
        body = "Short but complete blog post. " * 30  # ~900 chars, under 1500
        article_id = _insert(feed_id, "short post", "Teaser.")
        before = len(get_article_by_id(article_id).content)

        async def fake(url):
            return body

        monkeypatch.setattr(at, "fetch_article_content", fake)
        out = asyncio.run(at.ensure_article_text(get_article_by_id(article_id)))

        assert len(out) > before, "a materially better scrape was discarded"
        # Stored text is HTML-stripped, so compare lengths rather than the
        # exact string (trailing whitespace is normalised away).
        assert abs(len(get_article_by_id(article_id).content) - len(body)) <= 1

    def test_no_link_means_no_fetch(self, feed_id, monkeypatch):
        article_id = _insert(feed_id, "no link", "teaser", link="https://x.test/1")
        art = get_article_by_id(article_id)
        art.link = None

        async def must_not_run(url):
            raise AssertionError("fetched an article with no link")

        monkeypatch.setattr(at, "fetch_article_content", must_not_run)
        assert asyncio.run(at.ensure_article_text(art)) == "teaser"


class TestBackfillQuery:
    def test_finds_already_summarized_articles(self, feed_id):
        """The regression: the queue skips summarized articles entirely."""
        article_id = _insert(feed_id, "already summarized", "tiny teaser")
        update_article_summary(article_id, "An existing summary.", "llama3.2")

        found = [a.id for a in get_articles_needing_full_text(at.TEASER_MAX_LENGTH, 500)]
        assert article_id in found, (
            "an already-summarized teaser was not offered for backfill"
        )

    def test_skips_articles_that_are_already_full(self, feed_id):
        article_id = _insert(feed_id, "already complete", "Complete. " * 400)
        found = [a.id for a in get_articles_needing_full_text(at.TEASER_MAX_LENGTH, 500)]
        assert article_id not in found

    def test_skips_manual_links(self, feed_id):
        manual = create_feed(
            "https://manual.test/x.xml", "Manual Links", "others"
        ).id
        article_id = _insert(manual, "manual page", "teaser")
        found = [a.id for a in get_articles_needing_full_text(at.TEASER_MAX_LENGTH, 500)]
        assert article_id not in found


class TestScrapeIsBetter:
    """The gain rule.

    It originally also required a scrape to clear TEASER_MAX_LENGTH in
    absolute terms. That silently discarded good scrapes from sources whose
    posts are genuinely short — a Schneier entry stored 796 chars from the
    feed and scraped to 1037, a 30% improvement that never reached 1500, so it
    was rejected and re-attempted on every backfill run forever.
    """

    @staticmethod
    def _s(n):
        return "x" * n if n else None

    def test_short_post_can_still_improve(self):
        # The real regression: +241 chars, a 30% gain, under the 1500 floor.
        assert at.scrape_is_better(self._s(1037), self._s(796))

    def test_ratio_alone_is_enough(self):
        assert at.scrape_is_better(self._s(1000), self._s(796))

    def test_absolute_gain_alone_is_enough(self):
        assert at.scrape_is_better(self._s(5000), self._s(3000))

    def test_nothing_extracted_never_wins(self):
        assert not at.scrape_is_better(None, self._s(796))
        assert not at.scrape_is_better("", self._s(796))

    def test_partial_extraction_never_wins(self):
        assert not at.scrape_is_better(self._s(4), self._s(796))
        assert not at.scrape_is_better(self._s(500), self._s(796))

    def test_marginal_gain_is_rejected(self):
        # +104 chars is under both the 200 floor and the 1.2x ratio.
        assert not at.scrape_is_better(self._s(900), self._s(796))

    def test_anything_beats_nothing(self):
        assert at.scrape_is_better(self._s(500), None)


class TestBackfill:
    """End-to-end repairs against the real database.

    The job's own progress/concurrency/cancellation is covered in
    test_backfill_job.py; this pins that a run actually rewrites stored text.
    """

    def _run_job(self, monkeypatch, body):
        from app.lib.services.backfill import BackfillJob

        async def fake(url):
            return body

        monkeypatch.setattr(at, "fetch_article_content", fake)
        return asyncio.run(BackfillJob(concurrency=2).run())

    def test_repairs_teasers(self, feed_id, monkeypatch):
        ids = [
            _insert(feed_id, f"backfill target {i}", "tiny teaser")
            for i in range(3)
        ]
        for i in ids:
            update_article_summary(i, "already have a summary", "llama3.2")

        result = self._run_job(monkeypatch, "Scraped body. " * 300)

        assert result["repaired"] >= 3
        for i in ids:
            assert len(get_article_by_id(i).content) > at.TEASER_MAX_LENGTH

    def test_is_idempotent(self, feed_id, monkeypatch):
        article_id = _insert(feed_id, "idempotent target", "teaser")
        update_article_summary(article_id, "summary", "llama3.2")

        calls = {"n": 0}

        async def counting(url):
            calls["n"] += 1
            return "Long scraped body. " * 300

        monkeypatch.setattr(at, "fetch_article_content", counting)

        from app.lib.services.backfill import BackfillJob

        asyncio.run(BackfillJob(concurrency=2).run())
        first = calls["n"]

        # Second run must not re-fetch what the first repaired.
        asyncio.run(BackfillJob(concurrency=2).run())
        assert calls["n"] == first, "backfill re-fetched an already-repaired article"


class TestConsoleRoutes:
    """The Console's full-text endpoints are reachable and actually do something.

    These had no route-level test at all, so `POST /console/full-text-unblock`
    shipped calling a repository function it never imported: every click on
    "unblock" in the Console returned a bare 500 with no cause, because the
    job class was tested directly and the route was never exercised.
    """

    @pytest.fixture
    def client(self):
        from starlette.testclient import TestClient

        from app.main import app

        return TestClient(app, base_url="http://localhost")

    def test_unblock_clears_the_flag(self, client, feed_id):
        from app.db.models import Feed
        from app.db.repository import set_feed_full_text_blocked
        from app.db.session import SessionLocal

        set_feed_full_text_blocked(feed_id, True)

        resp = client.post("/api/console/full-text-unblock", params={"feed_id": feed_id})
        assert resp.status_code == 200, resp.text
        assert resp.json()["success"] is True

        with SessionLocal() as db:
            assert db.get(Feed, feed_id).full_text_blocked is None

    def test_unblock_requires_a_feed_id(self, client):
        # A bare click with no id used to be a 422 from FastAPI; assert it
        # stays a validation error rather than becoming a 500.
        assert client.post("/api/console/full-text-unblock").status_code == 422

    def test_backfill_status_responds(self, client):
        status = client.get("/api/console/backfill-full-text/status")
        assert status.status_code == 200
        assert "running" in status.json()

    def test_every_name_the_handlers_use_is_imported(self):
        """Pin the bug class directly: a handler calling a name it never imported.

        Cheap and blunt on purpose, and it covers endpoints no route test calls.
        The unblock button returned a bare 500 in the real app precisely because
        only the job class was tested and the route was never exercised.

        ``getclosurevars`` reports the global names a function actually
        references, so anything imported nowhere shows up here as missing.
        """
        import builtins
        import inspect

        from app.routers import console as console_router

        for fn in (
            console_router.full_text_unblock,
            console_router.backfill_full_text_endpoint,
        ):
            referenced = inspect.getclosurevars(fn).globals
            for name in referenced:
                if name in vars(builtins):
                    continue  # builtins aren't imports
                assert name in vars(console_router), (
                    f"{fn.__name__}() references {name!r}, which console.py never "
                    f"imports — calling it raises NameError at runtime"
                )

    def test_status_lists_blocked_feeds(self, client, feed_id):
        from app.db.repository import set_feed_full_text_blocked

        set_feed_full_text_blocked(feed_id, True)
        try:
            body = client.get("/api/console/full-text-status").json()
            assert any(f["id"] == feed_id for f in body["blockedFeeds"])
        finally:
            set_feed_full_text_blocked(feed_id, None)


class TestBothPathsAgree:
    def test_on_demand_path_uses_the_same_helper(self):
        """/api/summarize must go through ensure_article_text too."""
        import inspect

        from app.routers import summarize as summarize_router

        src = inspect.getsource(summarize_router.summarize_endpoint)
        assert "ensure_article_text" in src, (
            "the on-demand summarize path bypasses the shared text helper"
        )
        assert "len(article.content) > 10" not in src, (
            "the on-demand path still summarizes raw teaser text"
        )

    def test_scheduler_uses_the_same_helper(self):
        import inspect

        from app.lib.scheduler import summarizer

        src = inspect.getsource(summarizer.summarize_one)
        assert "ensure_article_text" in src