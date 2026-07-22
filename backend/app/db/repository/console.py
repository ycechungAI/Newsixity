"""Console / admin queries — port of queries.ts:1366-1685.

Covers the summarization queue, priority-based culling, and manual-link
article management (all of which reuse the SSRF/XSS guards from
app.lib.utils, matching queries.ts's createManualArticle exactly).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.models import Article as ArticleModel
from app.db.models import Category as CategoryModel
from app.db.models import Feed as FeedModel
from app.db.repository.helpers import Article, map_article_row
from app.db.session import SessionLocal
from app.lib.utils.sanitize import strip_html
from app.lib.utils.url import parse_http_url

CULL_UNSUMMARIZED_AGE_MONTHS = 6
CULL_SUMMARIZED_AGE_MONTHS = 12
CATEGORY_DAILY_INSERT_CAP = 20


@dataclass
class SummarizationQueueItem:
    id: int
    title: str
    feed_name: str
    category_slug: str
    published_at: str | None
    fetched_at: str


def delete_article_by_id(article_id: int) -> None:
    with SessionLocal() as db:
        db.execute(delete(ArticleModel).where(ArticleModel.id == article_id))
        db.commit()


def get_summarization_queue(limit: int = 20) -> list[SummarizationQueueItem]:
    with SessionLocal() as db:
        rows = db.execute(
            select(
                ArticleModel.id,
                ArticleModel.title,
                FeedModel.name.label("feed_name"),
                CategoryModel.slug.label("category_slug"),
                ArticleModel.published_at,
                ArticleModel.fetched_at,
            )
            .select_from(ArticleModel)
            .outerjoin(FeedModel, ArticleModel.feed_id == FeedModel.id)
            .outerjoin(CategoryModel, FeedModel.category_id == CategoryModel.id)
            .where(or_(ArticleModel.summary.is_(None), ArticleModel.summary == ""))
            .order_by(ArticleModel.fetched_at.desc())
            .limit(limit)
        ).all()

        return [
            SummarizationQueueItem(
                id=r.id,
                title=r.title,
                feed_name=r.feed_name or "Unknown",
                category_slug=r.category_slug or "unknown",
                published_at=r.published_at,
                fetched_at=r.fetched_at,
            )
            for r in rows
        ]


def _queue_count(db: Session) -> int:
    return db.execute(
        select(func.count(ArticleModel.id)).where(
            or_(ArticleModel.summary.is_(None), ArticleModel.summary == "")
        )
    ).scalar() or 0


def get_summarization_queue_count() -> int:
    with SessionLocal() as db:
        return _queue_count(db)


def cleanup_unsummarizable_articles() -> dict:
    """Remove articles that cannot be summarized: '[No content to summarize]'.

    These articles represent content that failed to extract/parse and cannot
    ever be summarized. They take up database space without value.

    Returns stats on deletion.
    """
    with SessionLocal() as db:
        result = db.execute(
            delete(ArticleModel).where(
                ArticleModel.summary == "[No content to summarize]"
            )
        )
        db.commit()

        deleted = result.rowcount or 0
        return {
            "deleted": deleted,
            "message": f"Deleted {deleted} articles that cannot be summarized",
        }


def cull_unsummarized_queue_to_limit(limit: int) -> int:
    """Keep up to `limit` unsummarized articles; cull the rest.

    Only ever culls unfavourited (is_saved=0) articles; never touches saved ones.
    Priority: (1) placeholder/failed summaries, (2) unsummarized, (3) old summarized.
    """
    deleted = 0

    with SessionLocal() as db:
        # 1) Cull "cannot summarized" placeholders (unfavourited, 6+ months).
        # NOTE: Only delete "[No content to summarize]" articles; keep "[Summarization failed:...]"
        # for users to review or manually retry. Failed articles should not be auto-deleted.
        cannot_ids = db.execute(
            select(ArticleModel.id)
            .where(
                ArticleModel.summary.like("[No content to summarize]%"),
                ArticleModel.is_saved == 0,
                func.coalesce(ArticleModel.published_at, ArticleModel.fetched_at)
                < func.datetime("now", f"-{CULL_UNSUMMARIZED_AGE_MONTHS} months"),
            )
            .order_by(ArticleModel.fetched_at.asc(), ArticleModel.id.asc())
            .limit(500)
        ).scalars().all()

        for article_id in cannot_ids:
            db.execute(delete(ArticleModel).where(ArticleModel.id == article_id))
            deleted += 1
        db.commit()

        # 2) Keep `limit` unsummarized; cull the rest one at a time (oldest first).
        while _queue_count(db) > limit:
            row = db.execute(
                select(ArticleModel.id)
                .where(
                    or_(ArticleModel.summary.is_(None), ArticleModel.summary == ""),
                    ArticleModel.is_saved == 0,
                    func.coalesce(ArticleModel.published_at, ArticleModel.fetched_at)
                    < func.datetime("now", f"-{CULL_UNSUMMARIZED_AGE_MONTHS} months"),
                )
                .order_by(ArticleModel.fetched_at.asc(), ArticleModel.id.asc())
                .limit(1)
            ).scalar_one_or_none()

            if row is None:
                break

            db.execute(delete(ArticleModel).where(ArticleModel.id == row))
            db.commit()
            deleted += 1

        # 3) Cull summarized, unfavourited articles older than 1 year (batch of 100).
        old_summarized_ids = db.execute(
            select(ArticleModel.id)
            .where(
                ArticleModel.summary.isnot(None),
                ArticleModel.summary != "",
                ArticleModel.is_saved == 0,
                func.coalesce(ArticleModel.published_at, ArticleModel.fetched_at)
                < func.datetime("now", f"-{CULL_SUMMARIZED_AGE_MONTHS} months"),
            )
            .order_by(ArticleModel.fetched_at.asc(), ArticleModel.id.asc())
            .limit(100)
        ).scalars().all()

        for article_id in old_summarized_ids:
            db.execute(delete(ArticleModel).where(ArticleModel.id == article_id))
            deleted += 1
        db.commit()

    return deleted


def remove_article_from_queue(article_id: int) -> None:
    with SessionLocal() as db:
        db.execute(
            update(ArticleModel)
            .where(ArticleModel.id == article_id)
            .values(summary="[Skipped: manually removed]", summary_model="skipped")
        )
        db.commit()


def get_category_articles_count_in_last_24h(category_slug: str) -> int:
    with SessionLocal() as db:
        return db.execute(
            select(func.count(ArticleModel.id))
            .select_from(ArticleModel)
            .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
            .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
            .where(
                CategoryModel.slug == category_slug,
                ArticleModel.fetched_at >= func.datetime("now", "-1 day"),
            )
        ).scalar() or 0


def get_manual_links_feed_id() -> int | None:
    with SessionLocal() as db:
        return db.execute(
            select(FeedModel.id).where(FeedModel.url == "internal://manual")
        ).scalar_one_or_none()


def create_manual_article(
    url: str,
    title: str,
    content: str | None = None,
    image_url: str | None = None,
    author: str | None = None,
) -> int | None:
    """Create an article from a manually-submitted link.

    Raises ValueError if the Manual Links feed is missing or the URL is
    unsafe (matches queries.ts throwing on both, rather than returning None).
    """
    feed_id = get_manual_links_feed_id()
    if not feed_id:
        raise ValueError("Manual Links feed not found")

    safe_url = parse_http_url(url)
    if not safe_url:
        raise ValueError("Manual links must use http/https URLs")

    safe_image_url = parse_http_url(image_url)
    safe_title = strip_html(title)[:500]
    safe_author = strip_html(author)[:200] if author else "Manual Entry"
    safe_content = strip_html(content)[:8000] if content else None

    url_hash = hashlib.sha256(safe_url.encode("utf-8")).hexdigest()
    guid = f"manual-{url_hash[:32]}"

    with SessionLocal() as db:
        stmt = (
            sqlite_insert(ArticleModel)
            .values(
                feed_id=feed_id,
                guid=guid,
                title=safe_title,
                link=safe_url,
                author=safe_author,
                published_at=func.datetime("now"),
                content=safe_content,
                image_url=safe_image_url,
            )
            .on_conflict_do_nothing(index_elements=["feed_id", "guid"])
        )
        result = db.execute(stmt)
        db.commit()

        if result.rowcount == 0:
            return None
        return result.inserted_primary_key[0] if result.inserted_primary_key else None


def delete_manual_article(article_id: int) -> bool:
    feed_id = get_manual_links_feed_id()
    if not feed_id:
        return False

    with SessionLocal() as db:
        result = db.execute(
            delete(ArticleModel).where(
                ArticleModel.id == article_id, ArticleModel.feed_id == feed_id
            )
        )
        db.commit()
        return result.rowcount > 0


def create_articles_from_search_results(
    results: list[dict],  # [{"title": str, "url": str, "description": str | None}]
    parent_url: str,
) -> list[int]:
    feed_id = get_manual_links_feed_id()
    if not feed_id or not results:
        return []

    parent_url_hash = hashlib.sha256(parent_url.encode("utf-8")).hexdigest()[:32]
    created_ids: list[int] = []

    with SessionLocal() as db:
        for result in results:
            safe_url = parse_http_url(result.get("url"))
            if not safe_url:
                continue

            safe_title = strip_html(result["title"])[:500]
            description = result.get("description")
            safe_description = strip_html(description)[:8000] if description else None

            # Derived from the result's own URL (not its list position) so
            # re-running the same search doesn't collide with a different
            # result landing on the same index. Prefix matches the parent
            # hash so getSearchResults' LIKE query finds these as children.
            result_url_hash = hashlib.sha256(safe_url.encode("utf-8")).hexdigest()[:16]
            guid = f"{parent_url_hash}-{result_url_hash}"

            stmt = (
                sqlite_insert(ArticleModel)
                .values(
                    feed_id=feed_id,
                    guid=guid,
                    title=safe_title,
                    link=safe_url,
                    author="Search Result",
                    published_at=func.datetime("now"),
                    content=safe_description,
                )
                .on_conflict_do_nothing(index_elements=["feed_id", "guid"])
            )
            insert_result = db.execute(stmt)

            if insert_result.rowcount > 0 and insert_result.inserted_primary_key:
                created_ids.append(insert_result.inserted_primary_key[0])

        db.commit()

    return created_ids


def get_search_results(article_url: str) -> list[Article]:
    feed_id = get_manual_links_feed_id()
    if not feed_id:
        return []

    url_hash = hashlib.sha256(article_url.encode("utf-8")).hexdigest()
    parent_guid = f"manual-{url_hash[:32]}"

    with SessionLocal() as db:
        parent = db.execute(
            select(ArticleModel.id).where(
                ArticleModel.feed_id == feed_id, ArticleModel.guid == parent_guid
            )
        ).scalar_one_or_none()

        if not parent:
            return []

        rows = db.execute(
            select(
                ArticleModel,
                FeedModel.name.label("feed_name"),
                CategoryModel.slug.label("category_slug"),
            )
            .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
            .join(CategoryModel, FeedModel.category_id == CategoryModel.id)
            .where(
                ArticleModel.feed_id == feed_id,
                ArticleModel.guid.like(f"{url_hash[:32]}-%"),
                ArticleModel.guid != parent_guid,
            )
            .limit(5)
        ).all()

        return [
            map_article_row({
                **r[0].__dict__,
                "feed_name": r.feed_name,
                "category_slug": r.category_slug,
            })
            for r in rows
        ]
