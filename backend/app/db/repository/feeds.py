"""Feed queries."""

from sqlalchemy import and_, func, select, update

from app.db.models import Category as CategoryModel
from app.db.models import Feed as FeedModel
from app.db.repository.helpers import Feed
from app.db.session import SessionLocal


def get_all_feeds() -> list[Feed]:
    """Get all feeds ordered by category sort_order and feed name."""
    with SessionLocal() as db:
        rows = db.execute(
            select(
                FeedModel,
                CategoryModel.slug.label("category_slug"),
            )
            .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
            .order_by(CategoryModel.sort_order, FeedModel.name)
        ).all()

        return [
            Feed(
                id=r[0].id,
                category_id=r[0].category_id,
                category_slug=r.category_slug,
                name=r[0].name,
                url=r[0].url,
                enabled=bool(r[0].enabled),
                last_fetched_at=r[0].last_fetched_at,
                last_error=r[0].last_error,
                source_weight=r[0].source_weight or 1.0,
            )
            for r in rows
        ]


def get_feed_category_slug(feed_id: int) -> str | None:
    """Get the category slug for a feed."""
    with SessionLocal() as db:
        row = db.execute(
            select(CategoryModel.slug)
            .join(FeedModel, FeedModel.category_id == CategoryModel.id)
            .where(FeedModel.id == feed_id)
        ).scalar_one_or_none()
        return row


def get_feeds_by_category(category_slug: str) -> list[Feed]:
    """Get all feeds for a category."""
    with SessionLocal() as db:
        rows = db.execute(
            select(FeedModel)
            .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
            .where(CategoryModel.slug == category_slug)
            .order_by(FeedModel.name)
        ).scalars().all()

        return [
            Feed(
                id=r.id,
                category_id=r.category_id,
                category_slug=category_slug,
                name=r.name,
                url=r.url,
                enabled=bool(r.enabled),
                last_fetched_at=r.last_fetched_at,
                last_error=r.last_error,
                source_weight=r.source_weight or 1.0,
            )
            for r in rows
        ]


def get_enabled_feeds() -> list[Feed]:
    """Get all enabled feeds (enabled = 1)."""
    with SessionLocal() as db:
        rows = db.execute(
            select(
                FeedModel,
                CategoryModel.slug.label("category_slug"),
            )
            .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
            .where(FeedModel.enabled == 1)
            .order_by(CategoryModel.sort_order, FeedModel.name)
        ).all()

        return [
            Feed(
                id=r[0].id,
                category_id=r[0].category_id,
                category_slug=r.category_slug,
                name=r[0].name,
                url=r[0].url,
                enabled=True,
                last_fetched_at=r[0].last_fetched_at,
                last_error=r[0].last_error,
                source_weight=r[0].source_weight or 1.0,
            )
            for r in rows
        ]


def update_feed_last_fetched(feed_id: int) -> None:
    """Update a feed's last_fetched_at timestamp and clear error."""
    with SessionLocal() as db:
        db.execute(
            update(FeedModel)
            .where(FeedModel.id == feed_id)
            .values(last_fetched_at=func.datetime("now"), last_error=None)
        )
        db.commit()


def update_feed_last_error(feed_id: int, error: str) -> None:
    """Update a feed's last_error message."""
    with SessionLocal() as db:
        db.execute(
            update(FeedModel)
            .where(FeedModel.id == feed_id)
            .values(last_error=error)
        )
        db.commit()
