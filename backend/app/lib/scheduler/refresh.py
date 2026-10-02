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
    get_category_articles_count_in_last_24h,
    get_feed_category_slug,
    upsert_article,
    CATEGORY_DAILY_INSERT_CAP,
)
from app.db.repository.helpers import Article
from app.lib.dedup.grouping import group_articles
from app.lib.dedup.similarity import hash_title, is_duplicate
from app.lib.integrations.rss import FeedResult, fetch_all_feeds_sync
from app.lib.ranking.promoter import score_and_promote_all
from app.lib.rss.feeds import seed_all_feeds, DEFAULT_FEEDS
from app.lib.scheduler.summarizer import background_summarize

logger = logging.getLogger("newsixity")


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
    count_start_by_category: dict[str, int] = {}
    inserted_this_session_by_category: dict[str, int] = {}
    new_articles_by_category: dict[str, list[int]] = {}
    existing_articles_by_category: dict[str, list[Article]] = {}

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

        # Seed the cap from what's already been stored in the last 24h.
        count_start_by_category[category_slug] = (
            get_category_articles_count_in_last_24h(category_slug)
        )

        # `category_slug` is bound as a default argument rather than closed over.
        # It is only ever called within this loop iteration today, so the
        # closure would work either way — but a bare closure over a loop
        # variable is the kind of thing that silently reads the *last* value
        # the moment someone moves a call outside the loop.
        def _cap_reached(
            slug: str = category_slug,
            start: int = count_start_by_category[category_slug],
        ) -> bool:
            return start + inserted_this_session_by_category.get(slug, 0) >= CATEGORY_DAILY_INSERT_CAP

        # Round-robin: each pass offers every feed in the category one
        # article, then moves to the next pass. A feed with a hundred entries
        # therefore can't outrank a feed with five.
        cursors = {i: 0 for i in range(len(category_feeds))}
        exhausted = False

        while not exhausted and not _cap_reached():
            exhausted = True

            for index, feed_result in enumerate(category_feeds):
                if _cap_reached():
                    break

                articles = feed_result.articles
                cursor = cursors[index]

                # Take exactly one article this pass; duplicates and
                # re-entries keep advancing the cursor without spending cap.
                while cursor < len(articles) and not _cap_reached():
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
                    # its FK here — skip that feed, don't abort the run.
                    try:
                        inserted_id = upsert_article(
                            feed_result.feed_id, asdict(parsed), title_hash
                        )
                    except IntegrityError as e:
                        errors.append(f"Feed {feed_result.feed_url}: {e.orig}")
                        break

                    if inserted_id:
                        new_articles += 1
                        inserted_this_session_by_category[category_slug] = (
                            inserted_this_session_by_category.get(category_slug, 0) + 1
                        )
                        new_articles_by_category.setdefault(category_slug, []).append(
                            inserted_id
                        )
                        # Newly inserted titles join the fuzzy-dedup pool so two
                        # feeds carrying the same story don't both land. Only
                        # .title is read from these, so a light record is enough.
                        existing_articles.append(
                            _TitleOnly(title=parsed.title)
                        )

                    break  # one article per feed per pass

                cursors[index] = cursor
                if cursor < len(articles):
                    exhausted = False

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
