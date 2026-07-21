"""Articles endpoints — /api/articles/*."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from app.lib.server.rate_limit import TEN_MIN_MS, rate_limit
from app.db.repository import (
    get_article_by_id,
    delete_article_by_id,
    mark_article_read,
    mark_article_unread,
    toggle_article_saved,
    get_articles_by_category,
    mark_all_read_by_category,
    upsert_article,
)
from app.schemas import Article, ManualArticleRequestBody, ArticlesMarkAllReadRequestBody

router = APIRouter()


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

            # If saving an unsummarized article, trigger background summarization
            # (Stage 7: hook into scheduler)
            updated = get_article_by_id(article_id)
            if updated and updated.is_saved and not updated.summary:
                pass  # Summarization trigger deferred to Stage 7

    article = get_article_by_id(article_id)
    return {"success": True, "category_slug": article.category_slug if article else None}


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

    return {"success": True, "category_slug": existing.category_slug}


@router.get("/articles")
async def list_articles(
    category: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[Article]:
    """List articles with optional category filter and pagination."""
    if category:
        articles = get_articles_by_category(category)
        return articles[offset : offset + limit]

    # TODO: implement global article listing (no category filter)
    return []


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
        image_url=body.image_url,
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
    category_slug = body.category_slug if body else None

    mark_all_read_by_category(category_slug)

    return {"success": True}
