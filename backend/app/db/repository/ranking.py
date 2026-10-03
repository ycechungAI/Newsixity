"""Article ranking & promotion queries — port of queries.ts:1686-1930."""

from __future__ import annotations

import json

from sqlalchemy import func, select, text, update

from app.db.models import Article as ArticleModel
from app.db.models import ArticleGroup as ArticleGroupModel
from app.db.models import Category as CategoryModel
from app.db.models import Feed as FeedModel
from app.db.session import SessionLocal

CAPPED_CATEGORIES = ["finance", "gaming", "sports", "world-news", "consumer-tech"]
DAILY_ARTICLE_LIMIT = 20
MAX_UNSUMMARIZED_QUEUE = 2000

# spec-v0.5 2.1 deleted FINANCE_DAILY_INSERT_CAP. It was exported and never
# read — the finance path went through CATEGORY_DAILY_INSERT_CAP like every
# other section. Per-feed caps (FEED_DAILY_SOFT_CAP / FEED_DAILY_HARD_CAP in
# app/lib/scheduler/refresh.py) replace both.

# Score weights as percentages that sum to 100 (spec-v0.5 5.4). These are the
# v0.4 literals, promoted to named constants so the defaults, the settings UI,
# and the regression guard in tests can't drift apart. score_article() takes
# them as parameters; a fresh install with no settings rows scores identically
# to v0.4.
DEFAULT_SCORE_WEIGHTS: dict[str, int] = {
    "groupSize": 30,
    "preferenceMatch": 30,
    "sourceWeight": 20,
    "recency": 10,
    "titleImportance": 10,
}

SCORE_WEIGHT_KEYS: tuple[str, ...] = tuple(DEFAULT_SCORE_WEIGHTS)


def update_article_score(article_id: int, score: float) -> None:
    with SessionLocal() as db:
        db.execute(
            update(ArticleModel)
            .where(ArticleModel.id == article_id)
            .values(relevance_score=score)
        )
        db.commit()


def update_article_scores(updates: list[dict]) -> None:
    """Batch score update. `updates` is [{"id": int, "score": float}, ...].

    An entry may also carry ``parts`` (the five components behind the total,
    spec-v0.5 6.1), which is stored as JSON. Entries without parts still
    update cleanly and leave any previously-recorded parts untouched, so a
    caller that only has a total isn't forced to erase the explanation.
    """
    with SessionLocal() as db:
        for u in updates:
            values: dict[str, object] = {"relevance_score": u["score"]}
            if "parts" in u:
                values["relevance_score_parts"] = json.dumps(u["parts"])
            db.execute(
                update(ArticleModel)
                .where(ArticleModel.id == u["id"])
                .values(**values)
            )
        db.commit()


def reset_promotion_for_category(category_slug: str) -> None:
    """Clear yesterday's promotions for a category (outside the ranking window)."""
    with SessionLocal() as db:
        db.execute(
            update(ArticleModel)
            .where(
                ArticleModel.is_promoted == 1,
                ArticleModel.feed_id.in_(
                    select(FeedModel.id)
                    .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
                    .where(CategoryModel.slug == category_slug)
                ),
                ~RECENT_WINDOW,
            )
            .values(is_promoted=0)
        )
        db.commit()


# The window ranking acts over, as a SQL fragment. spec-v0.5 1.3: scoring,
# promotion and the list's default sort must all mean the same "recent", or a
# score is computed against one window and promoted by another. Written once
# here because SQLite has no interval type to share — three copies of this
# expression drifting apart is exactly the failure this replaces.
#
# Anchored to coalesce(published_at, fetched_at): an article with no
# publication date is still recent if it was just fetched.
RECENT_WINDOW = text(
    "date(coalesce(published_at, fetched_at)) >= date('now', '-1 day')"
)


def promote_top_articles(category_slug: str, limit: int = DAILY_ARTICLE_LIMIT) -> None:
    """Clear recent promotions for the category, then promote the top-N by
    relevance_score over the same window scoring just used (spec-v0.5 1.3).

    Unscored articles are ordered after scored ones rather than alongside them:
    a NULL relevance_score sorting randomly into the promoted set is how a
    freshly-inserted, not-yet-scored article could take a "top" badge it was
    never a candidate for.
    """
    with SessionLocal() as db:
        category_feed_ids = select(FeedModel.id).join(
            CategoryModel, FeedModel.category_id == CategoryModel.id
        ).where(CategoryModel.slug == category_slug)

        # Clear promotions in the window.
        db.execute(
            update(ArticleModel)
            .where(
                ArticleModel.feed_id.in_(category_feed_ids),
                RECENT_WINDOW,
            )
            .values(is_promoted=0)
        )
        db.commit()

        # Promote top N by relevance score over the same window.
        top_ids = db.execute(
            select(ArticleModel.id)
            .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
            .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
            .where(
                CategoryModel.slug == category_slug,
                RECENT_WINDOW,
            )
            .order_by(
                ArticleModel.relevance_score.is_(None),
                ArticleModel.relevance_score.desc(),
                ArticleModel.id,
            )
            .limit(limit)
        ).scalars().all()

        if top_ids:
            db.execute(
                update(ArticleModel)
                .where(ArticleModel.id.in_(top_ids))
                .values(is_promoted=1)
            )
            db.commit()


def delete_unpromoted_articles_from_today(category_slug: str) -> int:
    """Disabled: kept for parity with queries.ts (deletion turned off there too)."""
    return 0


def get_article_group_size(article_id: int) -> int:
    with SessionLocal() as db:
        row = db.execute(
            select(ArticleGroupModel.article_count)
            .join(ArticleModel, ArticleModel.group_id == ArticleGroupModel.id)
            .where(ArticleModel.id == article_id)
        ).scalar_one_or_none()
        return row if row is not None else 1


def get_feed_source_weight(feed_id: int) -> float:
    with SessionLocal() as db:
        row = db.execute(
            select(FeedModel.source_weight).where(FeedModel.id == feed_id)
        ).scalar_one_or_none()
        return row if row is not None else 1.0


def update_feed_source_weight(feed_id: int, weight: float) -> None:
    """Set a feed's ranking weight.

    Raises FeedNotFoundError for an unknown id and ProtectedFeedError for the
    Manual Links feed (spec-v0.5 3.2, 3.3). Previously this was a bare
    ``UPDATE`` whose zero-row result was discarded, so a stale feedId returned
    ``{"success": true}``, persisted nothing, and the UI showed the change as
    applied — the select then snapped back with no explanation.
    """
    # Imported here to avoid a circular import: feeds.py doesn't import this
    # module at module scope, but the errors are defined alongside the other
    # feed-management errors so callers can map them uniformly.
    from app.db.repository.feeds import (
        MANUAL_FEED_URL,
        FeedNotFoundError,
        ProtectedFeedError,
    )

    with SessionLocal() as db:
        row = db.execute(
            select(FeedModel.id, FeedModel.url).where(FeedModel.id == feed_id)
        ).first()
        if row is None:
            raise FeedNotFoundError("Feed not found")
        if row.url == MANUAL_FEED_URL:
            raise ProtectedFeedError("The Manual Links feed can't be re-weighted")

        db.execute(
            update(FeedModel).where(FeedModel.id == feed_id).values(source_weight=weight)
        )
        db.commit()


def get_today_article_ids(category_slug: str) -> list[int]:
    """Ids in the ranking window for a category — what gets scored and promoted.

    Shares RECENT_WINDOW with promote_top_articles (spec-v0.5 1.3) so a score
    is never computed over a different set than the one it promotes from.
    """
    with SessionLocal() as db:
        rows = db.execute(
            select(ArticleModel.id)
            .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
            .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
            .where(
                CategoryModel.slug == category_slug,
                RECENT_WINDOW,
            )
            .order_by(ArticleModel.published_at.desc())
        ).scalars().all()
        return list(rows)


def get_promoted_article_count(category_slug: str) -> int:
    with SessionLocal() as db:
        return db.execute(
            select(func.count(ArticleModel.id))
            .select_from(ArticleModel)
            .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
            .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
            .where(CategoryModel.slug == category_slug, ArticleModel.is_promoted == 1)
        ).scalar() or 0
