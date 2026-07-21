"""Scoring + promotion pipeline — faithful port of src/lib/ranking/promoter.ts.

Scores all recent articles in a category and marks the top N as promoted.
DELETION IS DISABLED (as in the Node source): all articles are kept and visible.
"""

from __future__ import annotations

import logging

from app.db.repository import (
    CAPPED_CATEGORIES,
    DAILY_ARTICLE_LIMIT,
    get_today_article_ids,
    promote_top_articles,
)
from app.lib.ranking.scorer import score_articles_for_category

logger = logging.getLogger("newsixity")


def score_and_promote(category_slug: str, limit: int = DAILY_ARTICLE_LIMIT) -> None:
    """Run the full scoring + promotion pipeline for one category.

    Scores all articles from the last 24h, then promotes the top N by score.
    """
    article_ids = get_today_article_ids(category_slug)
    if not article_ids:
        return

    score_articles_for_category(category_slug, article_ids)
    promote_top_articles(category_slug, limit)

    # DELETION DISABLED — all articles remain visible in every category.
    logger.info("[Newsixity] Scored and promoted top %d articles in %s", limit, category_slug)


def score_and_promote_all() -> None:
    """Run scoring + promotion for every capped category (after a feed refresh)."""
    for slug in CAPPED_CATEGORIES:
        try:
            score_and_promote(slug)
        except Exception as e:  # noqa: BLE001 — parity with Node's per-slug try/catch.
            logger.warning("[Newsixity] Scoring error for %s: %s", slug, e)


def is_capped_category(slug: str) -> bool:
    """Whether a category has a daily article cap."""
    return slug in CAPPED_CATEGORIES
