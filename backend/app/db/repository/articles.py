"""Article queries — the largest section of queries.ts.

FLAGGED FOR SONNET REVIEW:
  * getArticleGroupsByCategory (lines 158–247): queries each group's articles
    and representative separately → N+1 queries (flag for batch JOIN).
  * getArticles*: multiple query patterns with optional sports filtering (complex LIKE).
"""

from hashlib import sha256

from sqlalchemy import and_, delete, func, or_, select, text, update
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
    """Mark articles stuck unsummarized for 8+ hours as timed out.

    Increased from 2 hours to allow local Ollama (fast but with high volume) to catch up.
    Articles still lacking a summary whose fetched_at is older than 8 hours get a
    "[Skipped: summarization timed out]" placeholder + 'skipped' model so it
    drops out of the queue. Returns the number of rows affected.
    """
    with SessionLocal() as db:
        result = db.execute(
            update(ArticleModel)
            .where(
                or_(ArticleModel.summary.is_(None), ArticleModel.summary == ""),
                ArticleModel.fetched_at < func.datetime("now", "-8 hours"),
            )
            .values(
                summary="[Skipped: summarization timed out]",
                summary_model="skipped",
            )
        )
        db.commit()
        return result.rowcount


def reset_failed_and_skipped_articles() -> dict:
    """Clear summary/summary_model for articles marked failed, skipped, or timed out,
    so the summarizer will retry them. Returns {"count": <rows affected>}."""
    with SessionLocal() as db:
        result = db.execute(
            update(ArticleModel)
            .where(
                or_(
                    ArticleModel.summary.like("[Summarization failed:%"),
                    ArticleModel.summary == "[No content to summarize]",
                    ArticleModel.summary == "[Skipped: summarization timed out]",
                )
            )
            .values(summary=None, summary_model=None)
        )
        db.commit()
        return {"count": result.rowcount}


def _calculate_engagement_score(article: ArticleModel, feed_weight: float = 1.0) -> float:
    """Calculate engagement score for an article (0-100).

    Higher scores = keep this article when choosing between duplicates.
    Factors:
    - Saved status (40 points)
    - Unread status (30 points)
    - Relevance/promotion (20 points)
    - Recency bonus (10 points)
    - No summary penalty (-20 points)
    """
    from datetime import datetime, timedelta

    score = 0.0

    # Saved articles should almost never be deleted
    if article.is_saved:
        score += 40

    # Unread articles are more valuable (user hasn't processed them yet)
    if not article.is_read:
        score += 30

    # Promoted/high-relevance articles are more valuable
    if article.is_promoted:
        score += 15
    if article.relevance_score and article.relevance_score > 0:
        score += min(5, article.relevance_score / 20)  # Cap at 5 points

    # Recency bonus: articles from last 7 days get +10, decreases with age
    if article.published_at:
        try:
            now = datetime.now()
            pub_date = datetime.fromisoformat(article.published_at.replace('Z', '+00:00'))
            days_old = (now - pub_date).days
            if days_old <= 7:
                score += 10
            elif days_old <= 30:
                score += 5
        except:
            pass

    # Articles without summary are less useful
    if not article.summary or article.summary == "":
        score -= 20

    # Feed quality (source_weight) provides small boost
    score += feed_weight - 1.0  # 0-based adjustment (1.0 = neutral)

    return max(0, min(100, score))  # Clamp to 0-100


def get_articles_with_scores() -> list[dict]:
    """Get all non-saved, read articles with their engagement scores.

    IMPORTANT: Only includes articles where is_saved == 0. Saved articles (favorites)
    are NEVER considered for any pruning strategy, regardless of score.

    Returns list of {id, title, score, published_at, feed_name} for scoring analysis.
    Used for threshold-based pruning preview.
    """
    with SessionLocal() as db:
        articles_with_feed = db.execute(
            select(
                ArticleModel.id,
                ArticleModel.title,
                ArticleModel.published_at,
                ArticleModel.is_saved,
                ArticleModel.is_read,
                ArticleModel.is_promoted,
                ArticleModel.relevance_score,
                ArticleModel.summary,
                FeedModel.name.label("feed_name"),
                FeedModel.source_weight.label("feed_weight"),
            )
            .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
            .where(
                and_(
                    ArticleModel.is_saved == 0,  # Only read, not saved
                    ArticleModel.is_read == 1,
                )
            )
        ).all()

        result = []
        for row in articles_with_feed:
            score = _calculate_engagement_score(
                type('Article', (), {
                    'is_saved': row.is_saved,
                    'is_read': row.is_read,
                    'is_promoted': row.is_promoted,
                    'relevance_score': row.relevance_score,
                    'published_at': row.published_at,
                    'summary': row.summary,
                })(),
                feed_weight=row.feed_weight or 1.0
            )
            result.append({
                "id": row.id,
                "title": row.title,
                "score": score,
                "published_at": row.published_at,
                "feed_name": row.feed_name,
            })

        return result


def get_prunable_articles(score_threshold: float = 0.0) -> dict:
    """Analyze articles for pruning and return a preview of what would be deleted.

    Strategies:
    1. Similarity-based: Group by title_hash, keep highest-scoring article per group
    2. Preserve user priorities: Never delete saved or unread articles
    3. Time-based: Delete articles >6 months old, but keep current year (2026)
    4. Skip articles without summaries
    5. Engagement scoring: Within duplicates, keep the most engaging article
    6. Score threshold: Delete any article with score < score_threshold (0-100)

    Args:
        score_threshold: Minimum engagement score to keep (0-100). Articles below this are deleted.

    Returns dict with:
    - total_articles: Total count
    - saved_count: Saved articles (preserved)
    - unread_count: Unread articles (preserved)
    - score_threshold: The threshold used
    - prunable_by_strategy: breakdown of articles to delete
    - preview_ids: Up to 100 article IDs that would be deleted
    - articles_by_score: Distribution of articles at each score level (for slider UI)
    """
    from datetime import datetime, timedelta

    with SessionLocal() as db:
        now = datetime.now()
        six_months_ago = now - timedelta(days=180)
        current_year_start = datetime(2026, 1, 1)

        # Total articles count
        total = db.execute(select(func.count(ArticleModel.id))).scalar() or 0

        # Saved articles (protected)
        saved = db.execute(
            select(func.count(ArticleModel.id)).where(ArticleModel.is_saved == 1)
        ).scalar() or 0

        # Unread articles (protected)
        unread = db.execute(
            select(func.count(ArticleModel.id)).where(ArticleModel.is_read == 0)
        ).scalar() or 0

        # Find similar articles by title_hash (exact duplicates)
        similar_candidates = db.execute(
            select(ArticleModel.title_hash, func.count(ArticleModel.id).label("count"))
            .where(
                and_(
                    ArticleModel.title_hash.isnot(None),
                    ArticleModel.title_hash != "",
                    ArticleModel.is_saved == 0,  # Skip saved
                    ArticleModel.is_read == 1,    # Only read articles
                )
            )
            .group_by(ArticleModel.title_hash)
            .having(func.count(ArticleModel.id) > 1)
        ).all()

        duplicates_to_delete = 0
        similar_ids = []

        for title_hash, count in similar_candidates:
            # Get all articles with this hash, including feed info for scoring
            articles_with_feed = db.execute(
                select(
                    ArticleModel,
                    FeedModel.source_weight.label("feed_weight"),
                )
                .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
                .where(ArticleModel.title_hash == title_hash)
            ).all()

            if articles_with_feed:
                # Score each article and keep the best one
                scored = [
                    {
                        "id": article.id,
                        "score": _calculate_engagement_score(article, feed_weight or 1.0),
                        "article": article,
                    }
                    for article, feed_weight in articles_with_feed
                ]

                # Sort by score descending (highest score first)
                scored.sort(key=lambda x: x["score"], reverse=True)

                # Keep the best, delete the rest
                best_id = scored[0]["id"]
                to_delete = [s["id"] for s in scored[1:]]

                duplicates_to_delete += len(to_delete)
                similar_ids.extend(to_delete[:50])  # Preview limit

        # Find old articles without summaries or with old timestamp
        old_articles = db.execute(
            select(ArticleModel.id)
            .where(
                and_(
                    ArticleModel.is_saved == 0,    # Not saved
                    ArticleModel.is_read == 1,      # Already read
                    ArticleModel.summary.isnot(None),  # Has summary
                    ArticleModel.summary != "",
                    ArticleModel.published_at < six_months_ago.isoformat(),  # Older than 6 months
                    ArticleModel.published_at < current_year_start.isoformat(),  # Before 2026
                )
            )
            .limit(100)
        ).scalars().all()

        old_count = db.execute(
            select(func.count(ArticleModel.id)).where(
                and_(
                    ArticleModel.is_saved == 0,
                    ArticleModel.is_read == 1,
                    ArticleModel.summary.isnot(None),
                    ArticleModel.summary != "",
                    ArticleModel.published_at < six_months_ago.isoformat(),
                    ArticleModel.published_at < current_year_start.isoformat(),
                )
            )
        ).scalar() or 0

        # Combine preview IDs (deduplicate)
        preview_ids = list(set(similar_ids + list(old_articles)))[:100]

        # Calculate score distribution for all read, non-saved articles
        score_distribution = {}
        below_threshold_ids = []
        below_threshold_count = 0

        if score_threshold > 0:
            articles_with_scores = get_articles_with_scores()
            for article_data in articles_with_scores:
                score = int(article_data["score"])
                score_distribution[score] = score_distribution.get(score, 0) + 1
                if article_data["score"] < score_threshold:
                    below_threshold_count += 1
                    if len(below_threshold_ids) < 100:
                        below_threshold_ids.append(article_data["id"])

        # Combine all deletion strategies
        total_threshold_deletions = below_threshold_count
        total_to_delete = duplicates_to_delete + old_count + total_threshold_deletions

        return {
            "total_articles": total,
            "saved_count": saved,
            "unread_count": unread,
            "score_threshold": score_threshold,
            "prunable_by_strategy": {
                "duplicates": duplicates_to_delete,
                "old_articles": old_count,
                "below_threshold": below_threshold_count,
                "total": total_to_delete,
            },
            "preview_ids": list(set(preview_ids + below_threshold_ids))[:100],
            "score_distribution": score_distribution if score_threshold > 0 else {},
        }


def prune_articles(score_threshold: float = 0.0) -> dict:
    """Execute article pruning: delete duplicates, old articles, and low-score articles.

    SAFETY GUARANTEE: Saved articles (favorites) are NEVER deleted under any strategy.
    This protection applies to all pruning strategies:
    - Duplicate removal: Saved articles are skipped entirely
    - Old article removal: Saved articles are skipped entirely
    - Score threshold: Only considers non-saved articles (is_saved == 0)

    Uses engagement scoring to keep the best article per duplicate cluster.
    Deletes any read/non-saved article with score < score_threshold.

    Args:
        score_threshold: Minimum engagement score to keep (0-100).

    Returns count of deleted articles by strategy.
    """
    from datetime import datetime, timedelta

    with SessionLocal() as db:
        now = datetime.now()
        six_months_ago = now - timedelta(days=180)
        current_year_start = datetime(2026, 1, 1)

        deleted_count = 0
        duplicates_deleted = 0

        # Delete duplicate articles (keeping the highest-scoring per title_hash)
        duplicates = db.execute(
            select(ArticleModel.title_hash, func.count(ArticleModel.id).label("count"))
            .where(
                and_(
                    ArticleModel.title_hash.isnot(None),
                    ArticleModel.title_hash != "",
                    ArticleModel.is_saved == 0,
                    ArticleModel.is_read == 1,
                )
            )
            .group_by(ArticleModel.title_hash)
            .having(func.count(ArticleModel.id) > 1)
        ).all()

        for title_hash, _ in duplicates:
            articles_with_feed = db.execute(
                select(
                    ArticleModel,
                    FeedModel.source_weight.label("feed_weight"),
                )
                .join(FeedModel, ArticleModel.feed_id == FeedModel.id)
                .where(ArticleModel.title_hash == title_hash)
            ).all()

            if articles_with_feed:
                # Score each article and keep the best one
                scored = [
                    {
                        "id": article.id,
                        "score": _calculate_engagement_score(article, feed_weight or 1.0),
                    }
                    for article, feed_weight in articles_with_feed
                ]

                # Sort by score descending
                scored.sort(key=lambda x: x["score"], reverse=True)

                # Keep the best, delete the rest
                to_delete = [s["id"] for s in scored[1:]]
                if to_delete:
                    db.execute(
                        delete(ArticleModel).where(ArticleModel.id.in_(to_delete))
                    )
                    deleted_count += len(to_delete)
                    duplicates_deleted += len(to_delete)

        # Delete old articles (count first)
        old_count_result = db.execute(
            delete(ArticleModel).where(
                and_(
                    ArticleModel.is_saved == 0,
                    ArticleModel.is_read == 1,
                    ArticleModel.summary.isnot(None),
                    ArticleModel.summary != "",
                    ArticleModel.published_at < six_months_ago.isoformat(),
                    ArticleModel.published_at < current_year_start.isoformat(),
                )
            )
        )

        old_count = old_count_result.rowcount or 0
        deleted_count += old_count

        # Delete articles below score threshold
        threshold_count = 0
        if score_threshold > 0:
            articles_with_scores = get_articles_with_scores()
            ids_to_delete = [a["id"] for a in articles_with_scores if a["score"] < score_threshold]

            if ids_to_delete:
                result = db.execute(
                    delete(ArticleModel).where(ArticleModel.id.in_(ids_to_delete))
                )
                threshold_count = result.rowcount or 0
                deleted_count += threshold_count

        db.commit()

        return {
            "deleted": deleted_count,
            "duplicates_deleted": duplicates_deleted,
            "old_articles_deleted": old_count,
            "threshold_deleted": threshold_count,
        }
