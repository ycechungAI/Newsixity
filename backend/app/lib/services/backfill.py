"""Backfill full article text for articles stored before scraping existed.

The summarization queue only visits *unsummarized* articles, so anything
summarized before full-text fetching existed kept its RSS teaser forever — on
this install 622 of 712 summarized articles were still teaser-length, which
made the article page's full-text view useless and left no fallback for when a
link later went stale.

Design notes, both learned the hard way here:

- **No up-front count.** An earlier version read all ~635 pending rows to size
  a progress bar. That was a full table scan before any work started, and the
  number it produced was wrong anyway — it counted paywalled and video articles
  that can never be scraped. The bar is now indeterminate until the run has
  fetched at least one batch.
- **Repairability is discovered, not predicted.** Nothing is skipped up front on
  a guess about which publishers paywall; each article is fetched and judged on
  what actually came back.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

from app.db.repository import (
    count_articles_needing_full_text,
    get_articles_needing_full_text,
    set_feed_full_text_blocked,
)
from app.lib.services.article_text import (
    TEASER_MAX_LENGTH,
    acquire_full_text,
)

logger = logging.getLogger("newsixity")

DEFAULT_BATCH_SIZE = 25

# Hard ceiling on how many articles may be in flight at once. A run usually
# contains many articles from a single feed (Al Jazeera alone has 80), and a
# dozen parallel requests to one host is what earns an IP block.
MAX_CONCURRENCY = 16


def default_concurrency() -> int:
    """How many articles to fetch at once, scaled to the machine.

    Fetching is network- and parse-bound, so it doesn't need a core each to run
    in parallel — but the parse step (trafilatura on a full page) is real CPU
    work, so scaling with core count still pays. Measured on an M4 Mac mini:
    sequential with a 1s politeness delay would take ~17 minutes for 600
    articles; 8-way concurrent takes ~50s.
    """
    cores = os.cpu_count() or 4
    return max(1, min(MAX_CONCURRENCY, 8 if cores >= 8 else cores))


DEFAULT_CONCURRENCY = default_concurrency()

# Small pause between batches. Enough to stay a polite client, negligible
# against the fetch time it sits in front of.
DEFAULT_DELAY_SECONDS = 0.05

# How many consecutive batches may repair nothing before the run gives up.
#
# The pending set is defined by *stored length*, so an article only leaves it
# when its text actually grows. Rows whose pages serve text that is already
# correct come back `served=True` with no gain — a success, not a miss — so
# their feed is never flagged as blocked and the rows are re-offered forever.
# The loop previously exited only on an *empty* batch, which those rows never
# produce: one full pass reported 900 processed against ~630 articles that
# existed, because `processed` counts fetch attempts, not distinct articles.
#
# Two consecutive idle batches, not one, so a single batch of network
# timeouts doesn't end a run that had just been making progress.
MAX_IDLE_BATCHES = 2

# How many articles a feed must fail to serve text for before it's flagged as
# unable to. High enough that a few dead links in an otherwise good feed don't
# condemn it; low enough that a blocked source is identified in one pass.
BLOCK_AFTER_MISSES = 5


class BackfillJob:
    """One backfill run, observable while it works and cancellable mid-flight."""

    def __init__(self, concurrency: int = DEFAULT_CONCURRENCY) -> None:
        self.concurrency = max(1, min(MAX_CONCURRENCY, concurrency))
        self.processed = 0
        self.repaired = 0
        self.skipped = 0
        self.total = 0
        self.current_feed: str | None = None
        self.running = False
        self.cancelled = False
        # Why the run ended early, when it did. None means it ran until the
        # pending set was exhausted, which is not the same thing as "nothing
        # was left to do" once an idle-batch stop is possible.
        self.stopped_reason: str | None = None
        self._idle_batches = 0
        self.finished_at: float | None = None
        self.started_at: float | None = None
        self.error: str | None = None
        # feed_id -> [articles that yielded text, articles that didn't]
        self._per_feed: dict[int, list[int]] = {}
        self._blocked_this_run: set[int] = set()

    @property
    def percent(self) -> int | None:
        """Percent complete, or None when there is nothing to divide by."""
        if not self.total:
            return None
        return min(100, round(self.processed * 100 / self.total))

    def snapshot(self) -> dict:
        return {
            "running": self.running,
            "cancelled": self.cancelled,
            "processed": self.processed,
            "repaired": self.repaired,
            "skipped": self.skipped,
            "total": self.total,
            "percent": self.percent,
            "concurrency": self.concurrency,
            "currentFeed": self.current_feed,
            "elapsedSeconds": round(time.monotonic() - self.started_at, 1)
            if self.started_at and self.running
            else None,
            "error": self.error,
            "stoppedReason": self.stopped_reason,
        }

    def cancel(self) -> None:
        """Ask the run to stop. Takes effect at the next batch boundary."""
        if self.running:
            self.cancelled = True
            logger.info("Full-text backfill: cancellation requested")

    def _reclassify_feeds(self) -> None:
        """Flag sources that served nothing, and unflag any that now work.

        This is what makes the pending count meaningful. Without it the count
        includes every paywalled and bot-blocked article forever: a full pass on
        this install processed 900 articles and repaired 3, yet the number never
        moved, because those 897 can never be scraped by anyone.

        A feed is blocked only after enough attempts with zero successes, so a
        single unlucky URL can't condemn a source. The reverse also holds: a
        feed that starts working is unflagged.
        """
        for feed_id, (wins, misses) in self._per_feed.items():
            if wins > 0 or misses == 0:
                # Served something, or hasn't been judged yet. Never block here.
                if feed_id in self._blocked_this_run:
                    set_feed_full_text_blocked(feed_id, None)
                    logger.info("Full-text backfill: %s is serving text again", feed_id)
                    self._blocked_this_run.discard(feed_id)
            elif misses >= BLOCK_AFTER_MISSES and feed_id not in self._blocked_this_run:
                set_feed_full_text_blocked(feed_id, True)
                self._blocked_this_run.add(feed_id)
                logger.info(
                    "Full-text backfill: blocking feed %s (%d articles, no text served)",
                    feed_id,
                    misses,
                )

    async def _repair_one(self, article) -> tuple[int, str, int, bool]:
        """Return (feed_id, feed_name, gained, served_text).

        The scrape decision lives in ``acquire_full_text`` so it cannot drift
        from the summarizer's. What this adds is ``served_text``, which the
        shared helper reports explicitly: "no gain" is ambiguous, and reading it
        as a refusal flagged 24 working feeds as blocked, including Ars
        Technica and Al Jazeera, whose stored text already matched the page.
        """
        before = len(article.content or "")
        result = await acquire_full_text(article)
        gained = max(0, len(result.text or "") - before)
        return article.feed_id, article.feed_name, gained, result.served

    async def run(self) -> dict:
        self.running = True
        self.cancelled = False
        self.error = None
        self.processed = self.repaired = self.skipped = 0
        self.total = 0
        self._idle_batches = 0
        self.stopped_reason = None
        self.started_at = time.monotonic()
        self.finished_at = None

        try:
            # One COUNT so the bar has a denominator, taken when the user
            # clicks Start rather than cached from page load. This is a single
            # aggregate — it does not materialize the rows, which is what the
            # earlier version did and what made it feel like duplicated effort.
            self.total = await asyncio.to_thread(
                count_articles_needing_full_text, TEASER_MAX_LENGTH
            )
            logger.info(
                "Full-text backfill starting: %d articles, concurrency %d",
                self.total,
                self.concurrency,
            )
            semaphore = asyncio.Semaphore(self.concurrency)

            async def guarded(article):
                async with semaphore:
                    return await self._repair_one(article)

            while not self.cancelled:
                articles = await asyncio.to_thread(
                    get_articles_needing_full_text, TEASER_MAX_LENGTH, DEFAULT_BATCH_SIZE
                )
                if not articles:
                    break

                # The total is only known once a batch comes back, and it only
                # becomes accurate as repaired articles drop out of the pending
                # set. Track it as "everything we have seen so far" rather than
                # paying for an up-front scan of rows we may never fetch.
                self.total = max(self.total, self.processed + len(articles))

                for a in articles:
                    self._per_feed.setdefault(a.feed_id, [0, 0])

                results = await asyncio.gather(*[guarded(a) for a in articles])

                repaired_this_batch = 0
                for feed_id, feed, gained, served in results:
                    self.processed += 1
                    if gained:
                        self.repaired += 1
                        repaired_this_batch += 1
                        if feed_id in self._per_feed:
                            self._per_feed[feed_id][0] += 1
                    elif not served:
                        # Only a fetch that returned nothing counts against the
                        # feed. "No gain because the text was already correct"
                        # is a success, not a refusal.
                        if feed_id in self._per_feed:
                            self._per_feed[feed_id][1] += 1
                    if feed:
                        self.current_feed = feed

                self._reclassify_feeds()

                # An idle batch means the next batch will be the same rows:
                # nothing grew, so nothing left the pending set. Counting
                # consecutive idles and stopping is what keeps `processed` a
                # count of articles rather than of HTTP requests.
                self._idle_batches = 0 if repaired_this_batch else self._idle_batches + 1

                logger.info(
                    "Full-text backfill: %d/%d processed, %d repaired",
                    self.processed,
                    self.total,
                    self.repaired,
                )

                if self.cancelled:
                    break

                if self._idle_batches >= MAX_IDLE_BATCHES:
                    self.stopped_reason = (
                        f"Stopped after {MAX_IDLE_BATCHES} batches with nothing "
                        f"repaired: {self.processed} articles checked, "
                        f"{self.repaired} repaired. The rest serve text that is "
                        f"already as good as it gets, or are unreachable."
                    )
                    logger.info("Full-text backfill: %s", self.stopped_reason)
                    break

                await asyncio.sleep(DEFAULT_DELAY_SECONDS)

        except Exception as exc:  # noqa: BLE001 — report, don't kill the server
            self.error = f"{type(exc).__name__}: {exc}"
            logger.exception("Full-text backfill failed")
        finally:
            self.running = False
            self.finished_at = time.monotonic()
            logger.info(
                "Full-text backfill finished: %d processed, %d repaired, %d skipped%s",
                self.processed,
                self.repaired,
                self.skipped,
                " (cancelled)" if self.cancelled else "",
            )

        return self.snapshot()


# Only one run at a time: a second would duplicate every fetch and double the
# traffic to each publisher for no benefit.
_active_job: BackfillJob | None = None


def get_active_job() -> BackfillJob | None:
    return _active_job


def start_job(concurrency: int = DEFAULT_CONCURRENCY) -> tuple[BackfillJob | None, str | None]:
    """Start a run. Returns (job, error). ``error`` is set if one is running."""
    global _active_job

    if _active_job is not None and _active_job.running:
        return None, "A full-text backfill is already running."

    _active_job = BackfillJob(concurrency=concurrency)
    _active_job._task = asyncio.create_task(_active_job.run())
    return _active_job, None