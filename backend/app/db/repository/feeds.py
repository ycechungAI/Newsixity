"""Feed queries."""

import json

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db.models import Article as ArticleModel
from app.db.models import ArticleGroup as ArticleGroupModel
from app.db.models import ArticleResearch as ArticleResearchModel
from app.db.models import Category as CategoryModel
from app.db.models import Feed as FeedModel
from app.db.models import Setting as SettingModel
from app.db.repository.helpers import Feed
from app.db.session import SessionLocal, reclaim_space


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


# ── User-managed feeds (v0.4) ─────────────────────────────────────────────

MANUAL_FEED_URL = "internal://manual"
# Seeded feed URLs the user deleted. init_db() re-seeds with INSERT OR IGNORE
# on every startup, so without this a deleted default feed came back on the
# next launch.
DELETED_FEED_URLS_KEY = "deleted_feed_urls"


class FeedError(ValueError):
    """Base for feed-management errors; the message is user-facing."""


class FeedNotFoundError(FeedError):
    pass


class ProtectedFeedError(FeedError):
    pass


class DuplicateFeedError(FeedError):
    pass


class UnknownCategoryError(FeedError):
    pass


def _feed_row(db, feed_id: int) -> Feed | None:
    row = db.execute(
        select(FeedModel, CategoryModel.slug.label("category_slug"))
        .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
        .where(FeedModel.id == feed_id)
    ).first()
    if row is None:
        return None
    f = row[0]
    return Feed(
        id=f.id,
        category_id=f.category_id,
        category_slug=row.category_slug,
        name=f.name,
        url=f.url,
        enabled=bool(f.enabled),
        last_fetched_at=f.last_fetched_at,
        last_error=f.last_error,
        source_weight=f.source_weight or 1.0,
    )


def _category_id(db, slug: str) -> int:
    category_id = db.execute(
        select(CategoryModel.id).where(CategoryModel.slug == slug)
    ).scalar_one_or_none()
    if category_id is None:
        raise UnknownCategoryError(f"Unknown category '{slug}'")
    return category_id


def get_deleted_feed_urls(db=None) -> set[str]:
    def read(session) -> set[str]:
        raw = session.execute(
            select(SettingModel.value).where(SettingModel.key == DELETED_FEED_URLS_KEY)
        ).scalar_one_or_none()
        try:
            urls = json.loads(raw) if raw else []
        except ValueError:
            urls = []
        return {u for u in urls if isinstance(u, str)}

    if db is not None:
        return read(db)
    with SessionLocal() as session:
        return read(session)


def _write_deleted_feed_urls(db, urls: set[str]) -> None:
    db.execute(
        sqlite_insert(SettingModel)
        .values(key=DELETED_FEED_URLS_KEY, value=json.dumps(sorted(urls)))
        .on_conflict_do_update(
            index_elements=["key"],
            set_={"value": json.dumps(sorted(urls)), "updated_at": func.datetime("now")},
        )
    )


def create_feed(url: str, name: str, category_slug: str) -> Feed:
    """Insert a feed. The caller has already probed `url` through the SSRF
    gate and confirmed it parses — this only does the bookkeeping."""
    with SessionLocal() as db:
        category_id = _category_id(db, category_slug)
        if db.execute(select(FeedModel.id).where(FeedModel.url == url)).first():
            raise DuplicateFeedError("That feed is already in your list")
        feed = FeedModel(category_id=category_id, name=name, url=url, enabled=1)
        db.add(feed)
        deleted = get_deleted_feed_urls(db)
        if url in deleted:
            # Re-adding by hand undoes the tombstone.
            _write_deleted_feed_urls(db, deleted - {url})
        db.commit()
        return _feed_row(db, feed.id)  # type: ignore[return-value]


def update_feed(
    feed_id: int,
    *,
    name: str | None = None,
    enabled: bool | None = None,
    category_slug: str | None = None,
) -> Feed:
    with SessionLocal() as db:
        feed = db.get(FeedModel, feed_id)
        if feed is None:
            raise FeedNotFoundError("Feed not found")
        if feed.url == MANUAL_FEED_URL:
            raise ProtectedFeedError("The Manual Links feed can't be changed")
        if name is not None:
            feed.name = name
        if enabled is not None:
            feed.enabled = 1 if enabled else 0
        if category_slug is not None:
            feed.category_id = _category_id(db, category_slug)
        db.commit()
        return _feed_row(db, feed_id)  # type: ignore[return-value]


def delete_feed(feed_id: int) -> dict:
    """Delete a feed and its unsaved articles; keep saved ones.

    Saved articles are reassigned to the Manual Links feed instead of being
    deleted — removing a source must never take the user's saved reading
    with it. Their guid is prefixed so it can't collide with a Manual Links
    guid on the (feed_id, guid) unique constraint. Research notes on deleted
    articles go too (FK), and topic groups left empty are removed; FTS5 stays
    in sync through the articles delete trigger.
    """
    with SessionLocal() as db:
        feed = db.get(FeedModel, feed_id)
        if feed is None:
            raise FeedNotFoundError("Feed not found")
        if feed.url == MANUAL_FEED_URL:
            raise ProtectedFeedError("The Manual Links feed can't be deleted")

        manual_id = db.execute(
            select(FeedModel.id).where(FeedModel.url == MANUAL_FEED_URL)
        ).scalar_one_or_none()

        group_ids = {
            g
            for (g,) in db.execute(
                select(ArticleModel.group_id).where(
                    ArticleModel.feed_id == feed_id, ArticleModel.group_id.is_not(None)
                )
            ).all()
        }

        kept = 0
        if manual_id is not None:
            kept = db.execute(
                update(ArticleModel)
                .where(ArticleModel.feed_id == feed_id, ArticleModel.is_saved == 1)
                .values(
                    feed_id=manual_id,
                    group_id=None,
                    guid=f"deleted-feed-{feed_id}:" + ArticleModel.guid,
                )
            ).rowcount

        doomed = select(ArticleModel.id).where(ArticleModel.feed_id == feed_id)
        db.execute(delete(ArticleResearchModel).where(ArticleResearchModel.article_id.in_(doomed)))
        deleted = db.execute(delete(ArticleModel).where(ArticleModel.feed_id == feed_id)).rowcount

        for group_id in group_ids:
            remaining = db.execute(
                select(ArticleModel.id)
                .where(ArticleModel.group_id == group_id)
                .order_by(ArticleModel.relevance_score.desc(), ArticleModel.id)
            ).scalars().all()
            if not remaining:
                db.execute(delete(ArticleGroupModel).where(ArticleGroupModel.id == group_id))
                continue
            group = db.get(ArticleGroupModel, group_id)
            if group is not None:
                group.article_count = len(remaining)
                if group.representative_id not in remaining:
                    group.representative_id = remaining[0]

        url = feed.url
        db.delete(feed)
        _write_deleted_feed_urls(db, get_deleted_feed_urls(db) | {url})
        db.commit()
        reclaim_space(db)
        return {"deletedArticles": deleted, "keptSavedArticles": kept}
