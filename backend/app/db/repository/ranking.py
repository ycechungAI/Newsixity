"""Article ranking & promotion queries — port of queries.ts:1686-1930."""

from __future__ import annotations

from sqlalchemy import func, select, update

from app.db.models import Article as ArticleModel
from app.db.models import ArticleGroup as ArticleGroupModel
from app.db.models import Category as CategoryModel
from app.db.models import Feed as FeedModel
from app.db.session import SessionLocal

CAPPED_CATEGORIES = ["finance", "gaming", "sports", "world-news"]
DAILY_ARTICLE_LIMIT = 20
FINANCE_DAILY_INSERT_CAP = 20
MAX_UNSUMMARIZED_QUEUE = 2000


def update_article_score(article_id: int, score: float) -> None:
    with SessionLocal() as db:
        db.execute(
            update(ArticleModel)
            .where(ArticleModel.id == article_id)
            .values(relevance_score=score)
        )
        db.commit()


def update_article_scores(updates: list[dict]) -> None:
    """Batch score update. `updates` is [{"id": int, "score": float}, ...]."""
    with SessionLocal() as db:
        for u in updates:
            db.execute(
                update(ArticleModel)
                .where(ArticleModel.id == u["id"])
                .values(relevance_score=u["score"])
            )
        db.commit()


def reset_promotion_for_category(category_slug: str) -> None:
    """Clear yesterday's promotions for a category (published before today)."""
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
                func.date(ArticleModel.published_at) < func.date("now"),
            )
            .values(is_promoted=0)
        )
        db.commit()


def promote_top_articles(category_slug: str, limit: int = DAILY_ARTICLE_LIMIT) -> None:
    """Clear today's promotions for the category, then promote the top-N by
    relevance_score from the last 24h."""
    with SessionLocal() as db:
        # Clear today's promotions for this category.
        db.execute(
            update(ArticleModel)
            .where(
                ArticleModel.feed_id.in_(
                    select(FeedModel.id)
                    .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
                    .where(CategoryModel.slug == category_slug)
                ),
                func.date(func.coalesce(ArticleModel.published_at, ArticleModel.fetched_at))
                >= func.date("now", "-1 day"),
            )
            .values(is_promoted=0)
        )
        db.commit()

        # Promote top N by relevance score from last 24h.
        top_ids = db.execute(
            select(ArticleModel.id)
            .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
            .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
            .where(
                CategoryModel.slug == category_slug,
                func.date(func.coalesce(ArticleModel.published_at, ArticleModel.fetched_at))
                >= func.date("now", "-1 day"),
            )
            .order_by(ArticleModel.relevance_score.desc())
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
    with SessionLocal() as db:
        db.execute(
            update(FeedModel).where(FeedModel.id == feed_id).values(source_weight=weight)
        )
        db.commit()


def get_today_article_ids(category_slug: str) -> list[int]:
    with SessionLocal() as db:
        rows = db.execute(
            select(ArticleModel.id)
            .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
            .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
            .where(
                CategoryModel.slug == category_slug,
                func.date(func.coalesce(ArticleModel.published_at, ArticleModel.fetched_at))
                >= func.date("now", "-1 day"),
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
