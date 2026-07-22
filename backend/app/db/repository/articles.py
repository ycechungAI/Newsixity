"""Article queries — the largest section of queries.ts.

FLAGGED FOR SONNET REVIEW:
  * getArticleGroupsByCategory (lines 158–247): queries each group's articles
    and representative separately → N+1 queries (flag for batch JOIN).
  * getArticles*: multiple query patterns with optional sports filtering (complex LIKE).
"""

from hashlib import sha256

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.models import Article as ArticleModel
from app.db.models import ArticleGroup as ArticleGroupModel
from app.db.models import Category as CategoryModel
from app.db.models import Feed as FeedModel
from app.db.repository.helpers import Article, map_article_row, SPORTS_KEYWORDS, SUMMARIZE_CATEGORY_PRIORITY
from app.db.session import SessionLocal
from app.lib.utils.sanitize import strip_html
from app.lib.utils.url import parse_http_url


def get_articles_by_category(
    slug: str | None = None,
    limit: int = 50,
    offset: int = 0,
    unread_only: bool = False,
    promoted_only: bool = False,
    saved_only: bool = False,
) -> list[Article]:
    """Get articles by category with optional filtering.

    Filters: category slug, unread-only, promoted-only, saved-only, and sports
    keyword filter if slug == "sports".
    """
    with SessionLocal() as db:
        query = (
            select(
                ArticleModel,
                FeedModel.name.label("feed_name"),
                CategoryModel.slug.label("category_slug"),
            )
            .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
            .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
        )

        conditions = []

        if slug:
            conditions.append(CategoryModel.slug == slug)

        if unread_only:
            conditions.append(ArticleModel.is_read == 0)

        if promoted_only:
            conditions.append(ArticleModel.is_promoted == 1)

        if saved_only:
            conditions.append(ArticleModel.is_saved == 1)

        # Sports filter: only basketball and Olympics
        if slug == "sports":
            sports_or = or_(
                *[ArticleModel.title.ilike(kw) for kw in SPORTS_KEYWORDS]
            )
            conditions.append(sports_or)

        if conditions:
            query = query.where(and_(*conditions))

        rows = db.execute(
            query.order_by(ArticleModel.is_read, ArticleModel.published_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()

        return [
            map_article_row({
                **row[0].__dict__,
                "feed_name": row.feed_name,
                "category_slug": row.category_slug,
            })
            for row in rows
        ]


def get_article_by_id(article_id: int) -> Article | None:
    """Get a single article by ID."""
    with SessionLocal() as db:
        row = db.execute(
            select(
                ArticleModel,
                FeedModel.name.label("feed_name"),
                CategoryModel.slug.label("category_slug"),
            )
            .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
            .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
            .where(ArticleModel.id == article_id)
        ).first()

        if not row:
            return None

        return map_article_row({
            **row[0].__dict__,
            "feed_name": row.feed_name,
            "category_slug": row.category_slug,
        })


def get_article_by_title_hash(
    title_hash: str, category_slug: str
) -> Article | None:
    """Get an article by title hash within the last 48 hours."""
    with SessionLocal() as db:
        row = db.execute(
            select(
                ArticleModel,
                FeedModel.name.label("feed_name"),
                CategoryModel.slug.label("category_slug"),
            )
            .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
            .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
            .where(
                and_(
                    ArticleModel.title_hash == title_hash,
                    CategoryModel.slug == category_slug,
                    ArticleModel.published_at >= func.datetime("now", "-48 hours"),
                )
            )
            .limit(1)
        ).first()

        if not row:
            return None

        return map_article_row({
            **row[0].__dict__,
            "feed_name": row.feed_name,
            "category_slug": row.category_slug,
        })


def get_saved_articles(
    limit: int = 50,
    offset: int = 0,
    category_slug: str | None = None,
) -> list[Article]:
    """Get saved (is_saved=1) articles."""
    with SessionLocal() as db:
        query = (
            select(
                ArticleModel,
                FeedModel.name.label("feed_name"),
                CategoryModel.slug.label("category_slug"),
            )
            .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
            .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
            .where(ArticleModel.is_saved == 1)
        )

        if category_slug:
            query = query.where(CategoryModel.slug == category_slug)

        rows = db.execute(
            query.order_by(ArticleModel.published_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()

        return [
            map_article_row({
                **row[0].__dict__,
                "feed_name": row.feed_name,
                "category_slug": row.category_slug,
            })
            for row in rows
        ]


def get_saved_article_count(category_slug: str | None = None) -> int:
    """Count saved articles, optionally by category."""
    with SessionLocal() as db:
        query = select(func.count(ArticleModel.id)).where(
            ArticleModel.is_saved == 1
        )

        if category_slug:
            query = (
                query.select_from(ArticleModel)
                .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
                .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
                .where(
                    and_(
                        ArticleModel.is_saved == 1,
                        CategoryModel.slug == category_slug,
                    )
                )
            )

        return db.execute(query).scalar() or 0


def search_articles(
    query_str: str,
    category: str | None = None,
    limit: int = 50,
) -> list[Article]:
    """Search articles by title."""
    with SessionLocal() as db:
        query = (
            select(
                ArticleModel,
                FeedModel.name.label("feed_name"),
                CategoryModel.slug.label("category_slug"),
            )
            .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
            .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
            .where(ArticleModel.title.ilike(f"%{query_str}%"))
        )

        if category:
            query = query.where(CategoryModel.slug == category)

        rows = db.execute(
            query.order_by(ArticleModel.published_at.desc()).limit(limit)
        ).all()

        return [
            map_article_row({
                **row[0].__dict__,
                "feed_name": row.feed_name,
                "category_slug": row.category_slug,
            })
            for row in rows
        ]


def upsert_article(
    feed_id: int,
    article: dict,  # ParsedArticle: guid, title, link, author, published_at, content, image_url
    title_hash: str,
) -> int | None:
    """Insert an article if it doesn't already exist (by feed_id, guid).

    Mirrors queries.ts upsertArticle exactly:
      * rejects non-http(s)/credential-bearing links (SSRF hardening)
      * strips HTML from title/author/content before storage (stored-XSS hardening)
      * uses INSERT OR IGNORE (atomic dedup on the (feed_id, guid) unique
        constraint) rather than check-then-insert, which would race under
        concurrent RSS refresh + summarizer writes.

    Returns the inserted article ID, or None if the link was unsafe or the
    (feed_id, guid) pair already existed.
    """
    safe_link = parse_http_url(article.get("link"))
    if not safe_link:
        return None

    safe_image_url = parse_http_url(article.get("image_url"))
    safe_title = strip_html(article["title"])[:500]
    raw_author = article.get("author")
    safe_author = strip_html(raw_author)[:200] if raw_author else None
    raw_content = article.get("content")
    safe_content = strip_html(raw_content)[:8000] if raw_content else None

    with SessionLocal() as db:
        stmt = (
            sqlite_insert(ArticleModel)
            .values(
                feed_id=feed_id,
                guid=article["guid"],
                title=safe_title,
                link=safe_link,
                author=safe_author,
                published_at=article.get("published_at"),
                content=safe_content,
                image_url=safe_image_url,
                title_hash=title_hash,
            )
            .on_conflict_do_nothing(index_elements=["feed_id", "guid"])
        )
        result = db.execute(stmt)
        db.commit()

        if result.rowcount == 0:
            return None
        return result.inserted_primary_key[0] if result.inserted_primary_key else None


def update_article_summary(article_id: int, summary: str, model: str) -> None:
    """Update an article's summary."""
    with SessionLocal() as db:
        db.execute(
            update(ArticleModel)
            .where(ArticleModel.id == article_id)
            .values(summary=summary, summary_model=model)
        )
        db.commit()


def update_article_content(article_id: int, content: str) -> None:
    """Update an article's content (HTML-stripped, matching queries.ts)."""
    safe_content = strip_html(content)[:8000] if content else None
    with SessionLocal() as db:
        db.execute(
            update(ArticleModel)
            .where(ArticleModel.id == article_id)
            .values(content=safe_content)
        )
        db.commit()


def mark_article_read(article_id: int) -> None:
    """Mark an article as read."""
    with SessionLocal() as db:
        article = db.execute(
            select(ArticleModel).where(ArticleModel.id == article_id)
        ).scalar_one_or_none()
        if article:
            article.is_read = 1
            db.commit()


def mark_article_unread(article_id: int) -> None:
    """Mark an article as unread."""
    with SessionLocal() as db:
        article = db.execute(
            select(ArticleModel).where(ArticleModel.id == article_id)
        ).scalar_one_or_none()
        if article:
            article.is_read = 0
            db.commit()


def mark_all_read_by_category(slug: str | None = None) -> int:
    """Mark all unread articles as read, optionally by category."""
    with SessionLocal() as db:
        if slug:
            stmt = (
                update(ArticleModel)
                .where(
                    and_(
                        ArticleModel.is_read == 0,
                        ArticleModel.feed_id.in_(
                            select(FeedModel.id).where(
                                FeedModel.category_id.in_(
                                    select(CategoryModel.id).where(
                                        CategoryModel.slug == slug
                                    )
                                )
                            )
                        ),
                    )
                )
                .values(is_read=1)
            )
        else:
            stmt = (
                update(ArticleModel)
                .where(ArticleModel.is_read == 0)
                .values(is_read=1)
            )

        result = db.execute(stmt)
        db.commit()
        return result.rowcount


def toggle_article_saved(article_id: int) -> None:
    """Toggle an article's saved status."""
    with SessionLocal() as db:
        article = db.execute(
            select(ArticleModel).where(ArticleModel.id == article_id)
        ).scalar_one_or_none()
        if article:
            article.is_saved = 1 - article.is_saved
            db.commit()


def get_unsummarized_articles(
    limit: int,
    category_slug: str | None = None,
) -> list[Article]:
    """Get unsummarized articles, optionally by category."""
    with SessionLocal() as db:
        query = (
            select(
                ArticleModel,
                FeedModel.name.label("feed_name"),
                CategoryModel.slug.label("category_slug"),
            )
            .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
            .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
            .where(ArticleModel.summary.is_(None))
        )

        if category_slug:
            query = query.where(CategoryModel.slug == category_slug)

        rows = db.execute(
            query.order_by(ArticleModel.published_at.desc()).limit(limit)
        ).all()

        return [
            map_article_row({
                **row[0].__dict__,
                "feed_name": row.feed_name,
                "category_slug": row.category_slug,
            })
            for row in rows
        ]


def get_unsummarized_saved_articles(limit: int = 30) -> list[Article]:
    """Get unsummarized saved articles (highest priority for summarization)."""
    with SessionLocal() as db:
        rows = db.execute(
            select(
                ArticleModel,
                FeedModel.name.label("feed_name"),
                CategoryModel.slug.label("category_slug"),
            )
            .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
            .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
            .where(
                and_(
                    ArticleModel.summary.is_(None),
                    ArticleModel.is_saved == 1,
                    ArticleModel.link.isnot(None),
                    ArticleModel.link != "",
                )
            )
            .order_by(ArticleModel.published_at.desc())
            .limit(limit)
        ).all()

        return [
            map_article_row({
                **row[0].__dict__,
                "feed_name": row.feed_name,
                "category_slug": row.category_slug,
            })
            for row in rows
        ]


def get_unsummarized_by_category(
    category_slug: str,
    limit: int = 30,
) -> list[Article]:
    """Get unsummarized articles for a specific category."""
    with SessionLocal() as db:
        rows = db.execute(
            select(
                ArticleModel,
                FeedModel.name.label("feed_name"),
                CategoryModel.slug.label("category_slug"),
            )
            .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
            .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
            .where(
                and_(
                    ArticleModel.summary.is_(None),
                    ArticleModel.is_saved == 0,
                    CategoryModel.slug == category_slug,
                    ArticleModel.link.isnot(None),
                    ArticleModel.link != "",
                )
            )
            .order_by(ArticleModel.published_at.desc())
            .limit(limit)
        ).all()

        return [
            map_article_row({
                **row[0].__dict__,
                "feed_name": row.feed_name,
                "category_slug": row.category_slug,
            })
            for row in rows
        ]


def get_recent_unsummarized_articles(
    since_minutes: int = 20,
    limit: int = 30,
) -> list[Article]:
    """Get recently fetched unsummarized articles."""
    with SessionLocal() as db:
        rows = db.execute(
            select(
                ArticleModel,
                FeedModel.name.label("feed_name"),
                CategoryModel.slug.label("category_slug"),
            )
            .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
            .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
            .where(
                and_(
                    ArticleModel.summary.is_(None),
                    ArticleModel.fetched_at > func.datetime("now", f"-{since_minutes} minutes"),
                    ArticleModel.link.isnot(None),
                    ArticleModel.link != "",
                )
            )
            .order_by(ArticleModel.is_saved.desc(), ArticleModel.published_at.desc())
            .limit(limit)
        ).all()

        return [
            map_article_row({
                **row[0].__dict__,
                "feed_name": row.feed_name,
                "category_slug": row.category_slug,
            })
            for row in rows
        ]


def get_summarize_category_priority() -> list[str]:
    """Get the category priority order for summarization."""
    return list(SUMMARIZE_CATEGORY_PRIORITY)


def mark_stuck_unsummarized_timed_out() -> int:
    """Mark articles stuck unsummarized for 2+ hours as timed out.

    Port of the pre-batch cleanup UPDATE in ollama/background.ts: any article
    still lacking a summary whose fetched_at is older than 2 hours gets a
    "[Skipped: summarization timed out]" placeholder + 'skipped' model so it
    drops out of the queue. Returns the number of rows affected.
    """
    with SessionLocal() as db:
        result = db.execute(
            update(ArticleModel)
            .where(
                or_(ArticleModel.summary.is_(None), ArticleModel.summary == ""),
                ArticleModel.fetched_at < func.datetime("now", "-2 hours"),
            )
            .values(
                summary="[Skipped: summarization timed out]",
                summary_model="skipped",
            )
        )
        db.commit()
        return result.rowcount


def reset_failed_and_skipped_articles() -> dict:
    """Clear summary/summary_model for articles marked failed or skipped, so
    the summarizer will retry them. Returns {"count": <rows affected>}."""
    with SessionLocal() as db:
        result = db.execute(
            update(ArticleModel)
            .where(
                or_(
                    ArticleModel.summary.like("[Summarization failed:%"),
                    ArticleModel.summary == "[No content to summarize]",
                )
            )
            .values(summary=None, summary_model=None)
        )
        db.commit()
        return {"count": result.rowcount}
