"""RSS feed refresh job — port of refreshAllFeeds in src/lib/rss/scheduler.ts.

Seeds default feeds, fetches every enabled feed, dedups new items by title hash
and fuzzy match, respects per-category daily insert caps, prioritizes finance
feeds, upserts articles, groups them per category, then scores + promotes.
The blocking pipeline runs in a worker thread via ``asyncio.to_thread`` so it
never stalls the event loop; the follow-up summarization is fired async,
fire-and-forget, exactly as Node does.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass

from sqlalchemy.exc import IntegrityError

from app.db.repository import (
    get_article_by_id,
    get_article_by_title_hash,
    get_articles_by_category,
    get_articles_by_ids,
    get_feed_article_count_in_last_24h,
    get_feed_category_slug,
    upsert_article,
)
from app.db.repository.helpers import Article
from app.lib.dedup.grouping import group_articles
from app.lib.dedup.similarity import hash_title, is_duplicate
from app.lib.integrations.rss import FeedResult, fetch_all_feeds_sync
from app.lib.ranking.promoter import score_and_promote_all
from app.lib.rss.feeds import seed_all_feeds, DEFAULT_FEEDS
from app.lib.scheduler.summarizer import background_summarize

logger = logging.getLogger("newsixity")

# Per-feed daily insert caps (spec-v0.5 2.2). These replace the per-section
# CATEGORY_DAILY_INSERT_CAP, which was first-come-first-served: the first feed
# processed drained the whole section budget and every other feed was silently
# skipped for the rest of the 24h window.
FEED_DAILY_SOFT_CAP = 5
FEED_DAILY_HARD_CAP = 8


@dataclass(frozen=True)
class _TitleOnly:
    """Just enough of an Article for the fuzzy-dedup pool.

    ``is_duplicate`` only reads ``.title``, so newly inserted titles are added
    to the pool as these rather than re-fetching full Article rows.
    """

    title: str


# Finance feed URL order for priority (top sources first).
FINANCE_FEED_URL_ORDER = [f["url"] for f in (DEFAULT_FEEDS.get("finance") or [])]


def _sort_feed_results_for_finance_priority(feed_results):
    """Sort results: finance feeds first (by order in DEFAULT_FEEDS), then others."""
    finance_results = []
    other_results = []

    for result in feed_results:
        category_slug = get_feed_category_slug(result.feed_id)
        if category_slug == "finance":
            finance_results.append(result)
        else:
            other_results.append(result)

    # Sort finance feeds by their order in FINANCE_FEED_URL_ORDER
    finance_results.sort(
        key=lambda r: FINANCE_FEED_URL_ORDER.index(r.feed_url)
        if r.feed_url in FINANCE_FEED_URL_ORDER
        else 999
    )

    return finance_results + other_results


def _run_feed_refresh_sync(
    category_filter: str | None = None,
) -> tuple[int, int, list[str]]:
    """
    The blocking half of the refresh: seed, fetch, dedup, upsert, group, score.
    Returns (refreshed_count, new_articles_count, errors).
    """
    seed_all_feeds()
    raw_feed_results = fetch_all_feeds_sync()

    # Sort for finance priority
    feed_results = _sort_feed_results_for_finance_priority(raw_feed_results)

    refreshed = 0
    new_articles = 0
    errors: list[str] = []
    inserted_this_session_by_feed: dict[int, int] = {}
    inserted_this_session_by_category: dict[str, int] = {}
    new_articles_by_category: dict[str, list[int]] = {}
    existing_articles_by_category: dict[str, list[Article]] = {}
    # feed_id -> which limit stopped it ("soft" / "hard"), so a refresh can
    # report a silenced feed instead of looking identical to a quiet one.
    capped_feeds: dict[int, str] = {}

    # Bucket usable feeds by category.
    #
    # Feeds were previously drained one at a time to completion, so in a
    # category with a shared daily budget the first feed to arrive consumed
    # the entire cap and every other feed was silently skipped for the rest of
    # the day — world-news showed nothing but Al Jazeera. Visiting feeds
    # round-robin instead gives each one a turn before any feed gets seconds.
    feeds_by_category: dict[str, list[FeedResult]] = {}
    for feed_result in feed_results:
        if feed_result.error:
            errors.append(f"Feed {feed_result.feed_url}: {feed_result.error}")
            continue

        refreshed += 1

        category_slug = get_feed_category_slug(feed_result.feed_id)
        if not category_slug:
            errors.append(
                f"Feed {feed_result.feed_url}: could not determine category"
            )
            continue

        if category_filter and category_slug != category_filter:
            continue

        feeds_by_category.setdefault(category_slug, []).append(feed_result)

    for category_slug, category_feeds in feeds_by_category.items():
        # Existing articles in this category, for fuzzy dedup.
        existing_articles_by_category[category_slug] = get_articles_by_category(
            category_slug, limit=200
        )

        # Per-feed starting positions in the rolling 24h window, plus the
        # section-wide fairness floor (spec-v0.5 2.3 / 2.4).
        #
        # `section_covered` is evaluated ONCE, before any insert. Computing it
        # live would let a feed that inserts its own 5th article raise the
        # floor mid-pass and starve feeds that had not yet had a turn.
        start_by_feed: dict[int, int] = {
            fr.feed_id: get_feed_article_count_in_last_24h(fr.feed_id)
            for fr in category_feeds
        }
        section_covered = all(v >= FEED_DAILY_SOFT_CAP for v in start_by_feed.values())

        # Round-robin: each pass offers every feed in the section one article,
        # then moves to the next pass, so a feed with a hundred entries cannot
        # outrank one with five.
        cursors = {i: 0 for i in range(len(category_feeds))}
        exhausted = False

        while not exhausted:
            exhausted = True

            for index, feed_result in enumerate(category_feeds):
                articles = feed_result.articles
                cursor = cursors[index]
                start = start_by_feed[feed_result.feed_id]
                inserted_here = inserted_this_session_by_feed.get(feed_result.feed_id, 0)

                # Take exactly one article this pass; duplicates and re-entries
                # advance the cursor without spending allowance (2.6).
                while cursor < len(articles):
                    # Hard cap, always enforced.
                    if start + inserted_here >= FEED_DAILY_HARD_CAP:
                        break
                    # Soft cap, gated on the whole section having met its floor.
                    # A feed still below the soft cap is always free to insert.
                    if start + inserted_here >= FEED_DAILY_SOFT_CAP and not section_covered:
                        break

                    parsed = articles[cursor]
                    cursor += 1

                    title_hash = hash_title(parsed.title)

                    # Exact title-hash duplicate.
                    if get_article_by_title_hash(title_hash, category_slug):
                        continue

                    # Fuzzy duplicate against existing article titles.
                    existing_articles = existing_articles_by_category[category_slug]
                    if any(
                        is_duplicate(parsed.title, existing.title)
                        for existing in existing_articles
                    ):
                        continue

                    # A feed the user deleted after this refresh started fails
                    # its FK here - skip that feed, don't abort the run.
                    try:
                        inserted_id = upsert_article(
                            feed_result.feed_id, asdict(parsed), title_hash
                        )
                    except IntegrityError as e:
                        errors.append(f"Feed {feed_result.feed_url}: {e.orig}")
                        break

                    if inserted_id:
                        new_articles += 1
                        inserted_here += 1
                        inserted_this_session_by_feed[feed_result.feed_id] = inserted_here
                        inserted_this_session_by_category[category_slug] = (
                            inserted_this_session_by_category.get(category_slug, 0) + 1
                        )
                        new_articles_by_category.setdefault(category_slug, []).append(
                            inserted_id
                        )
                        # Newly inserted titles join the fuzzy-dedup pool so two
                        # feeds carrying one story don't both land. Only .title
                        # is read from these, so a light record is enough.
                        existing_articles.append(_TitleOnly(title=parsed.title))

                    break  # one article per feed per pass

                cursors[index] = cursor
                # A feed blocked by a cap still has unread entries, but it is
                # not "work left to do" this pass - otherwise `exhausted` never
                # flips and the outer loop spins forever.
                blocked = (
                    start + inserted_here >= FEED_DAILY_HARD_CAP
                    or (start + inserted_here >= FEED_DAILY_SOFT_CAP and not section_covered)
                )
                if cursor < len(articles) and not blocked:
                    exhausted = False

                # 2.8: record a feed that stopped on a cap rather than running
                # dry, so "silenced" is distinguishable from "nothing new".
                if articles and blocked:
                    capped_feeds[feed_result.feed_id] = (
                        "hard"
                        if start + inserted_here >= FEED_DAILY_HARD_CAP
                        else "soft"
                    )

    # Group new articles by category.
    for slug, article_ids in new_articles_by_category.items():
        articles = get_articles_by_ids(article_ids)
        if articles:
            try:
                group_articles(articles, slug)
            except Exception as e:  # noqa: BLE001
                errors.append(f"Grouping error for {slug}: {e}")

    logger.info("[Newsixity] Feed refresh complete: %d refreshed, %d new articles", refreshed, new_articles)

    # Score and promote articles for capped categories.
    try:
        score_and_promote_all()
        logger.info("[Newsixity] Article scoring and promotion complete")
    except Exception as e:  # noqa: BLE001
        logger.warning("[Newsixity] Scoring/promotion error: %s", e)
        errors.append("Scoring/promotion error")

    return refreshed, new_articles, errors


async def _fire_background_summarize(limit: int = 10) -> None:
    """Run the summarizer without letting its errors escape (fire-and-forget)."""
    try:
        await background_summarize(limit)
    except Exception as e:  # noqa: BLE001
        logger.warning("[Newsixity] Background summarization error: %s", e)


async def refresh_all_feeds(category_filter: str | None = None) -> None:
    """Async entry point for the RSS refresh scheduler job."""
    try:
        await asyncio.to_thread(_run_feed_refresh_sync, category_filter)
    except Exception as e:  # noqa: BLE001
        logger.error("[Newsixity] Feed refresh error: %s", e)
        return

    # Background-summarize prioritized articles, fire-and-forget (matches Node).
    asyncio.create_task(_fire_background_summarize(10))
