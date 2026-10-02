"""Article group queries.

get_article_groups_by_category (SONNET REVIEW — resolved):
  Haiku's draft had two bugs, both fixed here:
  1. `func.count(case=[...])` used SQLAlchemy 1.x list-based `case()` syntax
     as a kwarg to `func.count()` — invalid, would raise at call time.
  2. The sports/promoted filters were applied against *any joined article
     row* in the group. queries.ts:176-198 filters via `EXISTS (... WHERE
     a_rep.id = ag.representative_id AND ...)` — i.e. against the group's
     REPRESENTATIVE article specifically, not an arbitrary member. A group
     whose representative isn't promoted but contains an unrelated promoted
     article would have been wrongly included.
  Also eliminated the N+1: the original queried each group's articles and
  representative in separate round-trips (1 + 2N total queries). This
  version batches articles and representatives across all groups into two
  IN(...) queries, for 3 queries total regardless of group count.
"""

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.orm import aliased

from app.db.models import Article as ArticleModel
from app.db.models import ArticleGroup as ArticleGroupModel
from app.db.models import Category as CategoryModel
from app.db.models import Feed as FeedModel
from app.db.repository.helpers import Article, ArticleGroup, map_article_row, SPORTS_KEYWORDS
from app.db.session import SessionLocal


def assign_article_to_group(article_id: int, group_id: int) -> None:
    """Assign an article to a group."""
    with SessionLocal() as db:
        article = db.execute(
            select(ArticleModel).where(ArticleModel.id == article_id)
        ).scalar_one_or_none()
        if article:
            article.group_id = group_id
            db.commit()


def create_group(
    label: str | None, category_id: int, representative_id: int
) -> int:
    """Create a new article group."""
    with SessionLocal() as db:
        group = ArticleGroupModel(
            label=label,
            category_id=category_id,
            representative_id=representative_id,
        )
        db.add(group)
        db.commit()
        db.refresh(group)
        return group.id


def update_group_representative(group_id: int, representative_id: int) -> None:
    """Update a group's representative article."""
    with SessionLocal() as db:
        db.execute(
            update(ArticleGroupModel)
            .where(ArticleGroupModel.id == group_id)
            .values(representative_id=representative_id, updated_at=func.datetime("now"))
        )
        db.commit()


def increment_group_count(group_id: int) -> None:
    """Increment the article count in a group (atomic SQL increment)."""
    with SessionLocal() as db:
        db.execute(
            update(ArticleGroupModel)
            .where(ArticleGroupModel.id == group_id)
            .values(
                article_count=ArticleGroupModel.article_count + 1,
                updated_at=func.datetime("now"),
            )
        )
        db.commit()


def get_recent_groups_by_category(
    category_slug: str,
    hours: int = 48,
) -> list[dict]:
    """Get recent groups in a category (for simple display)."""
    with SessionLocal() as db:
        rows = db.execute(
            select(
                ArticleGroupModel.id,
                ArticleGroupModel.label,
                ArticleGroupModel.category_id,
                ArticleModel.title.label("representative_title"),
                ArticleModel.content.label("representative_content"),
            )
            .join(CategoryModel, ArticleGroupModel.category_id == CategoryModel.id)
            .outerjoin(ArticleModel, ArticleGroupModel.representative_id == ArticleModel.id)
            .where(
                and_(
                    CategoryModel.slug == category_slug,
                    ArticleGroupModel.updated_at >= func.datetime("now", f"-{hours} hours"),
                )
            )
            .order_by(ArticleGroupModel.updated_at.desc())
        ).all()

        return [
            {
                "id": r.id,
                "label": r.label,
                "representative_title": r.representative_title,
                "representative_content": r.representative_content,
                "category_id": r.category_id,
            }
            for r in rows
        ]


def get_article_groups_by_category(
    slug: str | None = None,
    limit: int = 30,
    promoted_only: bool = False,
) -> list[ArticleGroup]:
    """Get article groups by category (batched — 3 queries total, no N+1).

    Filter semantics match queries.ts exactly: sports/promoted filters check
    the group's REPRESENTATIVE article, not any arbitrary member article.
    """
    ArticleRep = aliased(ArticleModel)

    with SessionLocal() as db:
        unread_count_subq = (
            select(func.count(ArticleModel.id))
            .where(
                ArticleModel.group_id == ArticleGroupModel.id,
                ArticleModel.is_read == 0,
            )
            .correlate(ArticleGroupModel)
            .scalar_subquery()
        )

        query = (
            select(ArticleGroupModel, unread_count_subq.label("unread_count"))
            .join(CategoryModel, ArticleGroupModel.category_id == CategoryModel.id)
        )

        conditions = []

        if slug:
            conditions.append(CategoryModel.slug == slug)

        if promoted_only:
            conditions.append(
                select(ArticleRep.id)
                .where(
                    ArticleRep.id == ArticleGroupModel.representative_id,
                    ArticleRep.is_promoted == 1,
                )
                .exists()
            )

        if slug == "sports":
            sports_or = or_(*[ArticleRep.title.ilike(kw) for kw in SPORTS_KEYWORDS])
            conditions.append(
                select(ArticleRep.id)
                .where(
                    ArticleRep.id == ArticleGroupModel.representative_id,
                    sports_or,
                )
                .exists()
            )

        if conditions:
            query = query.where(and_(*conditions))

        order_unread_flag = (
            select(func.count(ArticleModel.id))
            .where(
                ArticleModel.group_id == ArticleGroupModel.id,
                ArticleModel.is_read == 0,
            )
            .correlate(ArticleGroupModel)
            .scalar_subquery()
        ) > 0

        group_rows = db.execute(
            query.order_by(order_unread_flag.desc(), ArticleGroupModel.updated_at.desc())
            .limit(limit)
        ).all()

        if not group_rows:
            return []

        group_ids = [row[0].id for row in group_rows]
        rep_ids = [row[0].representative_id for row in group_rows if row[0].representative_id]

        # Batch-fetch every article belonging to any of these groups in one query.
        article_rows = db.execute(
            select(
                ArticleModel,
                FeedModel.name.label("feed_name"),
                CategoryModel.slug.label("category_slug"),
            )
            .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
            .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
            .where(ArticleModel.group_id.in_(group_ids))
            .order_by(ArticleModel.group_id, ArticleModel.is_read, ArticleModel.published_at.desc())
        ).all()

        articles_by_group: dict[int, list[Article]] = {}
        for r in article_rows:
            mapped = map_article_row({
                **r[0].__dict__,
                "feed_name": r.feed_name,
                "category_slug": r.category_slug,
            })
            articles_by_group.setdefault(r[0].group_id, []).append(mapped)

        # Batch-fetch every representative in one query.
        rep_by_id: dict[int, Article] = {}
        if rep_ids:
            rep_rows = db.execute(
                select(
                    ArticleModel,
                    FeedModel.name.label("feed_name"),
                    CategoryModel.slug.label("category_slug"),
                )
                .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
                .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
                .where(ArticleModel.id.in_(rep_ids))
            ).all()
            for r in rep_rows:
                rep_by_id[r[0].id] = map_article_row({
                    **r[0].__dict__,
                    "feed_name": r.feed_name,
                    "category_slug": r.category_slug,
                })

        result = []
        for row in group_rows:
            group = row[0]
            articles = articles_by_group.get(group.id, [])

            if not articles:
                continue

            representative = (
                rep_by_id.get(group.representative_id)
                if group.representative_id
                else None
            ) or articles[0]

            result.append(
                ArticleGroup(
                    id=group.id,
                    label=group.label,
                    category_id=group.category_id,
                    representative_id=group.representative_id,
                    article_count=group.article_count,
                    representative=representative,
                    articles=articles,
                )
            )

        return result
