"""Scoring + promotion pipeline — faithful port of src/lib/ranking/promoter.ts.

Scores all recent articles in a category and marks the top N as promoted.
DELETION IS DISABLED (as in the Node source): all articles are kept and visible.

Two changes from the port, both spec-v0.5:

* **§1.4** every category is scored, not only the previously-capped ones. That
  is what makes a feed weight mean something in *any* section, which in turn
  is why §4 can drop its hard-coded whitelist.
* **§5** the promote limit and the score weights come from per-section
  settings rather than module constants, and a section with ``ranked`` off is
  skipped entirely.
"""

from __future__ import annotations

import logging

from app.db.repository import (
    get_ranking_settings,
    get_today_article_ids,
    promote_top_articles,
)
from app.lib.ranking.scorer import score_articles_for_category

logger = logging.getLogger("newsixity")


def score_and_promote(category_slug: str, limit: int | None = None) -> None:
    """Run the full scoring + promotion pipeline for one category.

    Scores all articles from the last 24h, then promotes the top N by score.
    ``limit`` overrides the section's configured promote limit; ``None`` means
    "use the setting".
    """
    settings = get_ranking_settings(category_slug)
    if not settings.ranked:
        logger.debug("[Newsixity] %s is not ranked; skipping scoring", category_slug)
        return

    article_ids = get_today_article_ids(category_slug)
    if not article_ids:
        return

    score_articles_for_category(category_slug, article_ids, settings.weights)
    promote_top_articles(
        category_slug,
        limit if limit is not None else settings.promote_limit,
    )

    # DELETION DISABLED — all articles remain visible in every category.
    logger.info(
        "[Newsixity] Scored and promoted top %d articles in %s",
        limit if limit is not None else settings.promote_limit,
        category_slug,
    )


def score_and_promote_all() -> None:
    """Run scoring + promotion for every category, ranked or not (post-refresh).

    spec-v0.5 1.4: the v0.4 version looped CAPPED_CATEGORIES, so technology,
    security, top-news and the rest were never scored — which is the only
    reason the Feed Rankings UI had a whitelist to begin with. Every category
    is offered here; `score_and_promote` skips the ones with ranking off.
    """
    from app.db.repository.categories import get_categories

    for cat in get_categories():
        try:
            score_and_promote(cat.slug)
        except Exception as e:  # noqa: BLE001 — parity with Node's per-slug try/catch.
            logger.warning("[Newsixity] Scoring error for %s: %s", cat.slug, e)


def is_capped_category(slug: str) -> bool:
    """Whether a category is ranked (the v0.4 "capped" concept, spec-v0.5 1.4).

    Now a stored setting rather than a list literal, so Settings › Ranking can
    turn a section's ranking on or off.
    """
    return get_ranking_settings(slug).ranked


__all__ = [
    "score_and_promote",
    "score_and_promote_all",
    "is_capped_category",
]