"""Articles endpoints — /api/articles/*."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from app.lib.server.rate_limit import TEN_MIN_MS, rate_limit
from app.db.repository import (
    get_article_by_id,
    get_articles_by_ids,
    delete_article_by_id,
    mark_article_read,
    mark_article_unread,
    mark_articles_read,
    toggle_article_saved,
    get_articles_by_category,
    mark_all_read_by_category,
    upsert_article,
    get_prunable_articles,
    prune_articles,
    search_articles,
)
from app.schemas import (
    Article,
    ManualArticleRequestBody,
    ArticlesMarkAllReadRequestBody,
    ArticlesBulkMarkReadRequestBody,
)

router = APIRouter()


# MUST be declared before /articles/{article_id}: FastAPI matches routes in
# definition order, so a later /articles/search would be swallowed by the
# {article_id} route and fail as an invalid integer.
@router.get(
    "/articles/search",
    dependencies=[Depends(rate_limit("article-search", 120, TEN_MIN_MS))],
)
async def search(
    q: str = Query(..., min_length=1, max_length=200),
    category: Optional[str] = Query(None, max_length=80),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """Full-text search over article titles, bodies, and summaries.

    Backed by FTS5 with bm25 relevance ranking where available, falling back
    to a title-only LIKE scan otherwise (see repository.articles).
    """
    results = search_articles(q, category, limit, prefix=True)
    return {"query": q, "count": len(results), "articles": results}


@router.get(
    "/articles/{article_id}",
    response_model=Article,
    dependencies=[Depends(rate_limit("article-get", 240, TEN_MIN_MS))],
)
async def get_article(article_id: int) -> Article:
    """Fetch article by ID and mark as read."""
    if article_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid article ID")

    article = get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Mark as read automatically on fetch
    mark_article_read(article_id)

    return article


@router.patch(
    "/articles/{article_id}",
    dependencies=[Depends(rate_limit("article-patch", 120, TEN_MIN_MS))],
)
async def update_article(article_id: int, body: dict) -> dict:
    """Update article read/saved status."""
    if article_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid article ID")

    # Validate that at least one field is provided
    is_read = body.get("is_read")
    is_saved = body.get("is_saved")

    if is_read is None and is_saved is None:
        raise HTTPException(
            status_code=400, detail="At least one of is_read or is_saved must be provided"
        )

    existing = get_article_by_id(article_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Article not found")

    # Update read status
    if is_read is not None:
        if is_read:
            mark_article_read(article_id)
        else:
            mark_article_unread(article_id)

    # Update saved status
    if is_saved is not None:
        current = get_article_by_id(article_id)
        if current and current.is_saved != is_saved:
            toggle_article_saved(article_id)

            # If saving an unsummarized article, trigger background
            # summarization immediately (fire-and-forget), matching Node's
            # on-save summarizeArticleById call.
            updated = get_article_by_id(article_id)
            if updated and updated.is_saved and not updated.summary:
                import asyncio

                from app.lib.scheduler import summarize_article_by_id

                asyncio.create_task(summarize_article_by_id(article_id))

    article = get_article_by_id(article_id)
    return {"success": True, "categorySlug": article.category_slug if article else None}


@router.patch(
    "/articles",
    dependencies=[Depends(rate_limit("articles-bulk-patch", 60, TEN_MIN_MS))],
)
async def bulk_mark_articles_read(body: ArticlesBulkMarkReadRequestBody) -> dict:
    """Mark multiple articles as read in a single batched call.

    Used by ArticleCard's scroll-into-view auto-read tracking, which queues
    ids client-side instead of firing one PATCH per card.
    """
    if not body.articleIds:
        raise HTTPException(status_code=400, detail="articleIds must not be empty")

    articles_before = get_articles_by_ids(body.articleIds)
    mark_articles_read(body.articleIds)

    return {
        "success": True,
        "updated": [
            {"id": article.id, "categorySlug": article.category_slug}
            for article in articles_before
        ],
    }


@router.delete(
    "/articles/{article_id}",
    dependencies=[Depends(rate_limit("article-delete", 60, TEN_MIN_MS))],
)
async def delete_article(article_id: int) -> dict:
    """Delete article by ID."""
    if article_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid article ID")

    existing = get_article_by_id(article_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Article not found")

    delete_article_by_id(article_id)

    return {"success": True, "categorySlug": existing.category_slug}


@router.get("/articles")
async def list_articles(
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    saved: bool = Query(False),
) -> list[Article]:
    """List articles with optional category, saved, and pagination filters."""
    return get_articles_by_category(
        category, limit=limit, offset=offset, saved_only=saved, exclude_saved=not saved
    )


@router.post(
    "/articles/manual",
    dependencies=[Depends(rate_limit("manual-article-post", 60, TEN_MIN_MS))],
)
async def create_manual_article(body: ManualArticleRequestBody) -> Article:
    """Add a manual article (from console)."""
    from app.db.repository import create_manual_article as create_manual

    article_id = create_manual(
        url=body.url,
        title=body.title,
        content=body.content,
        image_url=body.imageUrl,
        author=body.author,
    )

    article = get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=500, detail="Failed to create article")

    return article


@router.post(
    "/articles/mark-all-read",
    dependencies=[Depends(rate_limit("articles-mark-all-read", 60, TEN_MIN_MS))],
)
async def mark_all_read(
    body: Optional[ArticlesMarkAllReadRequestBody] = None,
) -> dict:
    """Mark all articles as read (optionally for a specific category)."""
    category_slug = body.categorySlug if body else None

    marked = mark_all_read_by_category(category_slug)

    return {"success": True, "marked": marked}


@router.get(
    "/prune/preview",
    dependencies=[Depends(rate_limit("prune-preview", 60, TEN_MIN_MS))],
)
async def prune_preview(threshold: float = Query(0.0, ge=0, le=100)) -> dict:
    """Get a preview of articles that would be pruned.

    Args:
        threshold: Engagement score threshold (0-100). Articles below this are deleted.
    """
    return get_prunable_articles(score_threshold=threshold)


@router.post(
    "/prune",
    dependencies=[Depends(rate_limit("prune-execute", 60, TEN_MIN_MS))],
)
async def execute_prune(threshold: float = Query(0.0, ge=0, le=100)) -> dict:
    """Execute article pruning with score threshold.

    Args:
        threshold: Engagement score threshold (0-100). Articles below this are deleted.
    """
    result = prune_articles(score_threshold=threshold)
    return {"success": True, **result}
