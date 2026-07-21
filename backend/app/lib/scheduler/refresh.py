"""RSS feed refresh job — port of refreshAllFeeds in src/lib/rss/scheduler.ts.

Seeds default feeds, fetches every enabled feed, dedups new items by title hash,
upserts them, groups the new articles per category, then scores + promotes the
capped categories. The blocking pipeline (feedparser + SQLite) runs in a worker
thread via ``asyncio.to_thread`` so it never stalls the event loop; the
follow-up summarization is fired async, fire-and-forget, exactly as Node does.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict

from app.db.repository import (
    get_article_by_id,
    get_article_by_title_hash,
    get_feed_category_slug,
    upsert_article,
)
from app.db.repository.helpers import Article
from app.lib.dedup.grouping import group_articles
from app.lib.dedup.similarity import hash_title
from app.lib.integrations.rss import fetch_all_feeds_sync
from app.lib.ranking.promoter import score_and_promote_all
from app.lib.rss.feeds import seed_all_feeds
from app.lib.scheduler.summarizer import background_summarize

logger = logging.getLogger("newsixity")


def _run_feed_refresh_sync() -> None:
    """The blocking half of the refresh: seed, fetch, dedup, upsert, group, score."""
    seed_all_feeds()
    feed_results = fetch_all_feeds_sync()

    new_articles_by_category: dict[str, list[int]] = {}

    for feed_result in feed_results:
        if feed_result.error:
            continue

        category_slug = get_feed_category_slug(feed_result.feed_id)
        if not category_slug:
            continue

        for parsed in feed_result.articles:
            title_hash = hash_title(parsed.title)

            # Exact title-hash dedup within the category.
            if get_article_by_title_hash(title_hash, category_slug):
                continue

            inserted_id = upsert_article(feed_result.feed_id, asdict(parsed), title_hash)
            if inserted_id:
                new_articles_by_category.setdefault(category_slug, []).append(inserted_id)

    # Group new articles by category.
    for slug, article_ids in new_articles_by_category.items():
        articles: list[Article] = [
            a for a in (get_article_by_id(i) for i in article_ids) if a is not None
        ]
        if articles:
            group_articles(articles, slug)

    logger.info("[Newsixity] Feed refresh complete")

    # Score and promote articles for capped categories.
    try:
        score_and_promote_all()
        logger.info("[Newsixity] Article scoring and promotion complete")
    except Exception as e:  # noqa: BLE001
        logger.warning("[Newsixity] Scoring/promotion error: %s", e)


async def _fire_background_summarize(limit: int = 10) -> None:
    """Run the summarizer without letting its errors escape (fire-and-forget)."""
    try:
        await background_summarize(limit)
    except Exception as e:  # noqa: BLE001
        logger.warning("[Newsixity] Background summarization error: %s", e)


async def refresh_all_feeds() -> None:
    """Async entry point for the RSS refresh scheduler job."""
    try:
        await asyncio.to_thread(_run_feed_refresh_sync)
    except Exception as e:  # noqa: BLE001
        logger.error("[Newsixity] Feed refresh error: %s", e)
        return

    # Background-summarize prioritized articles, fire-and-forget (matches Node).
    asyncio.create_task(_fire_background_summarize(10))
