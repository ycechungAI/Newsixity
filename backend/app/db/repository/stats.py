"""Statistics and seeding queries."""

from sqlalchemy import and_, case, func, or_, select

from app.db.models import Article as ArticleModel
from app.db.models import Category as CategoryModel
from app.db.models import Feed as FeedModel
from app.db.repository.helpers import SPORTS_KEYWORDS
from app.db.session import SessionLocal


def get_article_count_by_category() -> list[dict]:
    """Get total and unread article counts per category.

    Counts exactly what ``get_articles_by_category`` will return for that
    category, because these numbers drive the sidebar badges *and* the page
    count. Two filters therefore have to match it:

    * **saved articles are excluded** — they live exclusively in the Saved
      tab, so counting them here inflated every category. Measured on a real
      database: world-news reported 176 while the list served 85 (91 saved),
      which showed as 6 pages where only 3 had any articles. Every category
      was affected.
    * **sports uses the keyword filter**, matching the list's behaviour.
    """
    with SessionLocal() as db:
        # An article counts toward its category only if the list would show
        # it: not saved, and for sports only when it matches a keyword.
        counts_toward_category = and_(
            ArticleModel.is_saved == 0,
            or_(
                CategoryModel.slug != "sports",
                or_(*[ArticleModel.title.ilike(kw) for kw in SPORTS_KEYWORDS]),
            ),
        )

        rows = db.execute(
            select(
                CategoryModel.slug,
                func.count(
                    case((counts_toward_category, ArticleModel.id))
                ).label("total"),
                func.sum(
                    case(
                        (
                            and_(counts_toward_category, ArticleModel.is_read == 0),
                            1,
                        ),
                        else_=0,
                    )
                ).label("unread"),
            )
            .select_from(CategoryModel)
            .outerjoin(FeedModel, FeedModel.category_id == CategoryModel.id)
            .outerjoin(ArticleModel, ArticleModel.feed_id == FeedModel.id)
            .group_by(CategoryModel.slug)
            .order_by(CategoryModel.sort_order)
        ).all()

        return [
            {
                "slug": r.slug,
                "total": r.total or 0,
                "unread": r.unread or 0,
            }
            for r in rows
        ]


def seed_feed(category_slug: str, name: str, url: str) -> None:
    """Seed a feed into a category."""
    with SessionLocal() as db:
        category = db.execute(
            select(CategoryModel).where(CategoryModel.slug == category_slug)
        ).scalar_one_or_none()

        if not category:
            raise ValueError(f'Category "{category_slug}" not found')

        # INSERT OR IGNORE
        existing = db.execute(
            select(FeedModel).where(
                and_(
                    FeedModel.category_id == category.id,
                    FeedModel.name == name,
                    FeedModel.url == url,
                )
            )
        ).scalar_one_or_none()

        if not existing:
            new_feed = FeedModel(
                category_id=category.id,
                name=name,
                url=url,
            )
            db.add(new_feed)
            db.commit()
