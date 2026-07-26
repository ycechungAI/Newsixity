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
from dataclasses import asdict

from app.db.repository import (
    get_article_by_id,
    get_article_by_title_hash,
    get_articles_by_category,
    get_articles_by_ids,
    get_category_articles_count_in_last_24h,
    get_feed_category_slug,
    upsert_article,
    CATEGORY_DAILY_INSERT_CAP,
)
from app.db.repository.helpers import Article
from app.lib.dedup.grouping import group_articles
from app.lib.dedup.similarity import hash_title, is_duplicate
from app.lib.integrations.rss import fetch_all_feeds_sync
from app.lib.ranking.promoter import score_and_promote_all
from app.lib.rss.feeds import seed_all_feeds, DEFAULT_FEEDS
from app.lib.scheduler.summarizer import background_summarize

logger = logging.getLogger("newsixity")

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
    count_start_by_category: dict[str, int] = {}
    inserted_this_session_by_category: dict[str, int] = {}
    new_articles_by_category: dict[str, list[int]] = {}
    existing_articles_by_category: dict[str, list[Article]] = {}

    for feed_result in feed_results:
        if feed_result.error:
            errors.append(f"Feed {feed_result.feed_url}: {feed_result.error}")
            continue

        refreshed += 1

        # Look up the category slug for this feed
        category_slug = get_feed_category_slug(feed_result.feed_id)
        if not category_slug:
            errors.append(
                f"Feed {feed_result.feed_url}: could not determine category"
            )
            continue

        # If a category filter was provided, skip feeds not in that category
        if category_filter and category_slug != category_filter:
            continue

        # Get existing articles in this category for fuzzy dedup.
        if category_slug not in existing_articles_by_category:
            existing_articles_by_category[category_slug] = get_articles_by_category(
                category_slug, limit=200
            )

        for parsed in feed_result.articles:
            # Cap all categories at CATEGORY_DAILY_INSERT_CAP new articles per 24h
            if category_slug not in count_start_by_category:
                count_start_by_category[category_slug] = (
                    get_category_articles_count_in_last_24h(category_slug)
                )

            inserted_this_session = (
                inserted_this_session_by_category.get(category_slug) or 0
            )

            if (
                count_start_by_category[category_slug] + inserted_this_session
                >= CATEGORY_DAILY_INSERT_CAP
            ):
                continue

            title_hash = hash_title(parsed.title)

            # Check for exact title hash duplicate
            if get_article_by_title_hash(title_hash, category_slug):
                continue

            # Check for fuzzy duplicate against existing article titles
            existing_articles = existing_articles_by_category[category_slug]
            if any(is_duplicate(parsed.title, existing.title) for existing in existing_articles):
                continue

            # Insert the article
            inserted_id = upsert_article(feed_result.feed_id, asdict(parsed), title_hash)

            if inserted_id:
                new_articles += 1
                inserted_this_session_by_category[category_slug] = (
                    inserted_this_session_by_category.get(category_slug, 0) + 1
                )
                new_articles_by_category.setdefault(category_slug, []).append(inserted_id)

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
