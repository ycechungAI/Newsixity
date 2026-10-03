"""The full-text backfill job: progress, concurrency, cancellation.

Replaces the one-batch-per-click design, which meant repairing ~600 articles
meant clicking a button 60 times.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.lib.services import article_text as at
from app.lib.services.backfill import (
    BackfillJob,
    DEFAULT_BATCH_SIZE,
    MAX_CONCURRENCY,
    default_concurrency,
)


def _s(n):
    return "x" * n if n else None


class TestBlockedFeedTracking:
    """A source that serves nothing gets excluded, so the count stays honest.

    Measured motivation: a full pass over 900 articles repaired 3, yet the
    pending count never moved, because the rest are paywalled or bot-blocked
    (Politico and NPR 403 every request regardless of User-Agent).
    """

    def _article(self, i, feed_id, name="Feed"):
        return type("A", (), {
            "id": i, "feed_id": feed_id, "feed_name": name,
            "content": "teaser", "link": f"https://x.test/{i}",
        })()

    def test_feeder_is_blocked_after_enough_misses(self, monkeypatch):
        from app.lib.services.backfill import BLOCK_AFTER_MISSES

        marked = []

        async def nothing(url):
            return ""  # paywalled / blocked

        monkeypatch.setattr("app.lib.services.article_text.fetch_article_content", nothing)
        monkeypatch.setattr(
            "app.lib.services.backfill.set_feed_full_text_blocked",
            lambda fid, blocked: marked.append((fid, blocked)),
        )

        blocked_feed = 7
        articles = [
            self._article(i, blocked_feed if i < BLOCK_AFTER_MISSES else 99)
            for i in range(BLOCK_AFTER_MISSES + 2)
        ]
        served = {"batches": 0}

        def fake_get(_threshold, limit):
            served["batches"] += 1
            if served["batches"] > 1:
                return []
            return articles[:limit]

        monkeypatch.setattr(
            "app.lib.services.backfill.get_articles_needing_full_text", fake_get
        )
        monkeypatch.setattr(
            "app.lib.services.backfill.count_articles_needing_full_text",
            lambda _max_length=None: len(articles),
        )

        job = BackfillJob(concurrency=2)
        asyncio.run(job.run())

        assert (blocked_feed, True) in marked, (
            f"feed {blocked_feed} served nothing across "
            f"{BLOCK_AFTER_MISSES} articles but was not flagged"
        )

    def test_already_correct_articles_do_not_block_their_feed(self, monkeypatch):
        """The bug this distinction exists for.

        "No gain" is ambiguous: a paywalled fetch returns nothing, and an
        article that was already correct also gains nothing because the fetch
        came back identical. Counting the second as a refusal flagged 24 working
        feeds as blocked — including Ars Technica and Al Jazeera, whose stored
        text matched the page exactly (1410 stored, 1410 fetched).
        """
        from app.lib.services.backfill import BLOCK_AFTER_MISSES

        marked = []

        async def returns_same(url):
            # The feed serves fine; the stored text is already what it returns.
            return "x" * 1200

        monkeypatch.setattr(
            "app.lib.services.article_text.fetch_article_content", returns_same
        )
        monkeypatch.setattr(
            "app.lib.services.backfill.set_feed_full_text_blocked",
            lambda fid, blocked: marked.append((fid, blocked)),
        )

        working_feed = 3
        articles = [
            type("A", (), {
                "id": i, "feed_id": working_feed, "feed_name": "Ars Technica",
                "content": "x" * 1200,   # already correct
                "link": f"https://x.test/{i}",
            })()
            for i in range(BLOCK_AFTER_MISSES + 3)
        ]
        served = {"batches": 0}

        def fake_get(_threshold, limit):
            served["batches"] += 1
            if served["batches"] > 1:
                return []
            return articles[:limit]

        monkeypatch.setattr(
            "app.lib.services.backfill.get_articles_needing_full_text", fake_get
        )
        monkeypatch.setattr(
            "app.lib.services.backfill.count_articles_needing_full_text",
            lambda _max_length=None: len(articles),
        )

        asyncio.run(BackfillJob(concurrency=2).run())

        assert not any(fid == working_feed and blocked for fid, blocked in marked), (
            "a feed whose articles were already correct was wrongly blocked"
        )

    def test_a_working_feed_is_not_blocked(self, monkeypatch):
        marked = []

        async def good(url):
            return "Full body. " * 400

        monkeypatch.setattr("app.lib.services.article_text.fetch_article_content", good)
        monkeypatch.setattr(
            "app.lib.services.backfill.set_feed_full_text_blocked",
            lambda fid, blocked: marked.append((fid, blocked)),
        )

        articles = [self._article(i, 5) for i in range(6)]
        served = {"batches": 0}

        def fake_get(_threshold, limit):
            served["batches"] += 1
            if served["batches"] > 1:
                return []
            return articles[:limit]

        monkeypatch.setattr(
            "app.lib.services.backfill.get_articles_needing_full_text", fake_get
        )
        monkeypatch.setattr(
            "app.lib.services.backfill.count_articles_needing_full_text",
            lambda _max_length=None: len(articles),
        )

        asyncio.run(BackfillJob(concurrency=2).run())

        assert not any(fid == 5 and blocked for fid, blocked in marked), (
            "a feed that serves text was wrongly blocked"
        )


class TestConcurrencyDefault:
    def test_scales_with_cores_and_is_capped(self):
        """Never more than MAX, never zero, always at least 1."""
        import os

        cores = os.cpu_count() or 4
        expected = max(1, min(MAX_CONCURRENCY, 8 if cores >= 8 else cores))
        assert default_concurrency() == expected

    def test_never_exceeds_the_ceiling(self):
        assert default_concurrency() <= MAX_CONCURRENCY
        assert default_concurrency() >= 1


class TestGainRule:
    """Regression: an absolute 1500-char floor discarded good short scrapes.

    A Schneier entry stored 796 chars and scraped to 1037 — a 30% gain that
    never reached 1500, so it was rejected and re-attempted on every run.
    """

    def test_short_post_can_improve(self):
        assert at.scrape_is_better(_s(1037), _s(796))

    def test_ratio_alone_is_enough(self):
        assert at.scrape_is_better(_s(1000), _s(796))

    def test_absolute_gain_alone_is_enough(self):
        assert at.scrape_is_better(_s(5000), _s(3000))

    def test_worse_text_never_wins(self):
        assert not at.scrape_is_better(_s(500), _s(796))
        assert not at.scrape_is_better(_s(4), _s(796))
        assert not at.scrape_is_better(None, _s(796))
        assert not at.scrape_is_better("", _s(796))

    def test_marginal_gain_rejected(self):
        # +104 chars: under the 200 floor and under the 1.2x ratio.
        assert not at.scrape_is_better(_s(900), _s(796))

    def test_anything_beats_nothing(self):
        assert at.scrape_is_better(_s(500), None)


def _run_bounded(job, timeout: float):
    """Run a job with a hard deadline, so a runaway loop fails the test loudly."""
    async def _go():
        return await asyncio.wait_for(job.run(), timeout=timeout)

    try:
        return asyncio.run(_go())
    except asyncio.TimeoutError as exc:
        pytest.fail(
            f"the backfill was still running after {timeout}s "
            f"({job.processed} attempts): it is re-fetching rows that never "
            f"leave the pending set instead of stopping"
        )
        raise AssertionError from exc


class TestNoProgressStopsTheRun:
    """The run must stop when a batch repairs nothing.

    `get_articles_needing_full_text` selects by *stored length*, so an article
    stays in the pending set unless its stored text actually grows. A publisher
    whose pages serve text that is already correct (`served=True`, no gain) is
    never flagged as blocked — a success is not a miss — so those rows are
    re-offered on every single batch, forever.

    The symptom is a backfill that "fetches" far more articles than exist:
    `processed` counts fetch *attempts*, not distinct articles. Measured on
    this install: a pass reported 900 processed while only ~630 articles were
    ever pending.

    articles.py already documents the intended rule — "it stops when a batch
    comes back with no progress" — and the loop implemented something weaker,
    exiting only on an *empty* batch, which those rows never produce.
    """

    def _article(self, i):
        return type("A", (), {
            "id": i, "feed_id": 7, "feed_name": "Working publisher",
            "content": "short but correct", "link": f"https://x.test/{i}",
        })()

    def test_run_stops_instead_of_refetching_the_same_rows_forever(self, monkeypatch):
        articles = [self._article(i) for i in range(25)]
        batches = {"n": 0}

        def fake_get(_threshold, limit):
            batches["n"] += 1
            # Always hand back the same pending rows — what the real query does
            # when nothing grew. No artificial cap: the point is that the job,
            # not the fixture, has to end the run.
            return articles[:limit]

        monkeypatch.setattr(
            "app.lib.services.backfill.get_articles_needing_full_text", fake_get
        )
        monkeypatch.setattr(
            "app.lib.services.backfill.count_articles_needing_full_text",
            lambda *a, **k: len(articles),
        )
        # The fetch "succeeds" and returns exactly what is already stored.
        monkeypatch.setattr(
            "app.lib.services.backfill.acquire_full_text",
            lambda a: asyncio.sleep(
                0, result=type("R", (), {"text": "short but correct", "served": True})()
            ),
        )

        job = BackfillJob(concurrency=2)
        # Bounded on purpose. Without a no-progress stop this never returns —
        # the rows are re-offered forever — and a hanging test reports far less
        # clearly than a timeout naming the cause.
        snap = _run_bounded(job, 5.0)

        assert snap["repaired"] == 0
        assert batches["n"] <= 3, (
            f"the run kept re-offering the same {len(articles)} articles "
            f"{batches['n']} times instead of stopping"
        )
        assert snap["processed"] <= len(articles) * 2, (
            f"processed {snap['processed']} fetch attempts for only "
            f"{len(articles)} articles — attempts are being counted as articles"
        )

    def test_the_run_says_why_it_stopped(self, monkeypatch):
        """A run that ends early must not look like a finished one.

        Otherwise "0 repaired" is indistinguishable from "there was nothing to
        do", which is the same silent-failure class this repo keeps hitting.
        """
        articles = [self._article(i) for i in range(5)]

        monkeypatch.setattr(
            "app.lib.services.backfill.get_articles_needing_full_text",
            lambda _t, limit: articles[:limit],
        )
        monkeypatch.setattr(
            "app.lib.services.backfill.count_articles_needing_full_text",
            lambda *a, **k: len(articles),
        )
        monkeypatch.setattr(
            "app.lib.services.backfill.acquire_full_text",
            lambda a: asyncio.sleep(0, result=type("R", (), {"text": "short but correct", "served": True})()),
        )

        snap = _run_bounded(BackfillJob(concurrency=2), 5.0)

        assert snap["stoppedReason"], "an early stop reported no reason"
        assert "repair" in snap["stoppedReason"].lower()


class TestBackfillJob:
    def test_progress_is_monotonic_and_ends_complete(self, monkeypatch):
        class FakeArticle:
            def __init__(self, i):
                self.id = i
                self.feed_id = i % 3
                self.feed_name = f"feed{i % 3}"
                self.content = "teaser"
                self.link = f"https://x.test/{i}"

        articles = [FakeArticle(i) for i in range(30)]

        async def fake(url):
            await asyncio.sleep(0.001)
            return "Full body. " * 200

        monkeypatch.setattr("app.lib.services.article_text.fetch_article_content", fake)

        job = BackfillJob(concurrency=4)

        # The job asks for the full pending set once (to size the bar), then asks
        # for batches. Serve the work on the first *batch* call, not the count
        # call, and report empty afterwards so the run terminates.
        served = {"batches": 0}

        def fake_get(threshold, limit):
            start = served["batches"] * DEFAULT_BATCH_SIZE
            served["batches"] += 1
            return articles[start : start + limit]

        monkeypatch.setattr(
            "app.lib.services.backfill.get_articles_needing_full_text", fake_get
        )
        # The job also takes one COUNT at start for the bar's denominator.
        monkeypatch.setattr(
            "app.lib.services.backfill.count_articles_needing_full_text",
            lambda _max_length=None: len(articles),
        )

        snap = asyncio.run(job.run())

        # 30 articles at 25 per batch is two rounds; an empty third ends it.
        assert job.processed == 30
        assert job.repaired == 30
        assert snap["percent"] == 100
        assert snap["running"] is False

    def test_cancel_stops_early(self, monkeypatch):
        """Cancel must actually halt, not just set a flag that is ignored."""
        calls = {"n": 0}
        batches = []

        def fake_get(threshold, limit):
            # Hand out work forever so only cancellation can end the run.
            if len(batches) > 5:
                return []
            batches.append(1)
            return [
                type("A", (), {
                    "id": calls["n"], "feed_id": 1, "feed_name": "f",
                    "content": "teaser",
                    "link": f"https://x.test/{calls['n']}",
                })()
                for _ in range(5)
            ]

        async def fake(url):
            calls["n"] += 1
            await asyncio.sleep(0.005)
            return "Body. " * 300

        monkeypatch.setattr("app.lib.services.article_text.fetch_article_content", fake)
        monkeypatch.setattr(
            "app.lib.services.backfill.get_articles_needing_full_text", fake_get
        )
        monkeypatch.setattr(
            "app.lib.services.backfill.count_articles_needing_full_text",
            lambda _max_length=None: 999,
        )

        async def scenario():
            job = BackfillJob(concurrency=2)
            task = asyncio.create_task(job.run())
            await asyncio.sleep(0.05)
            job.cancel()
            return await asyncio.wait_for(task, timeout=5)

        snap = asyncio.run(scenario())

        assert snap["cancelled"] is True
        assert snap["running"] is False
        assert snap["processed"] < 30, "cancel did not stop the sweep early"

    def test_percent_handles_zero_total(self):
        """None, not 0 — an unknown total must not read as "0% done"."""
        job = BackfillJob()
        assert job.percent is None
        assert job.snapshot()["percent"] is None

    def test_running_jobs_reflect_state(self):
        job = BackfillJob(concurrency=3)
        job.running = True
        job.started_at = time.monotonic()
        job.total = 10
        job.processed = 5
        snap = job.snapshot()
        assert snap["percent"] == 50
        assert snap["concurrency"] == 3
        assert snap["elapsedSeconds"] is not None