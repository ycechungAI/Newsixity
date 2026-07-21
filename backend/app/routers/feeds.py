"""Feeds endpoints — /api/feeds/*."""

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.repository import get_all_feeds, update_feed_source_weight, CAPPED_CATEGORIES
from app.schemas import Feed, FeedWeightUpdateRequestBody
from app.lib.integrations import fetch_all_feeds
from app.lib.scheduler.refresh import _run_feed_refresh_sync
from app.lib.scheduler.summarizer import background_summarize
from app.lib.server.rate_limit import TEN_MIN_MS, rate_limit

router = APIRouter()


@router.get(
    "/feeds",
    response_model=list[Feed],
    dependencies=[Depends(rate_limit("feeds-get", 180, TEN_MIN_MS))],
)
async def list_feeds() -> list[Feed]:
    """Get all feeds with metadata."""
    feeds = get_all_feeds()
    return feeds


@router.post(
    "/feeds/refresh",
    dependencies=[Depends(rate_limit("feeds-refresh", 6, TEN_MIN_MS))],
)
async def refresh_feeds(category: Optional[str] = Query(None)) -> dict:
    """Trigger RSS feed refresh with optional category filter.

    Implements the full Node algorithm: finance-priority sorting,
    per-category daily caps, exact+fuzzy dedup, grouping, and promotion.
    Returns {refreshed, newArticles, errors} matching the Node RefreshResult.
    Fires background summarization after completion (fire-and-forget).
    """
    if category and category not in CAPPED_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {', '.join(CAPPED_CATEGORIES)}",
        )

    # Run the full refresh algorithm synchronously (blocking in thread pool)
    try:
        refreshed, new_articles, errors = await asyncio.to_thread(
            _run_feed_refresh_sync, category
        )
    except Exception as e:
        import logging
        logging.error("[Newsixity] Feed refresh error: %s", e)
        return {"refreshed": 0, "newArticles": 0, "errors": [f"Internal error: {e}"]}

    # Fire-and-forget background summarization after refresh completes (matches Node)
    async def fire_summarize():
        try:
            await background_summarize(10)
        except Exception as e:
            import logging
            logging.warning("[Newsixity] Background summarization error: %s", e)

    asyncio.create_task(fire_summarize())

    return {"refreshed": refreshed, "newArticles": new_articles, "errors": errors}


@router.put(
    "/feeds/weights",
    dependencies=[Depends(rate_limit("feeds-weights-patch", 60, TEN_MIN_MS))],
)
async def update_feed_weights(body: FeedWeightUpdateRequestBody) -> dict:
    """Update source weight for a feed."""
    if body.weight < 0.1 or body.weight > 10.0:
        raise HTTPException(status_code=400, detail="Weight must be between 0.1 and 10.0")

    update_feed_source_weight(body.feed_id, body.weight)

    return {"success": True, "feed_id": body.feed_id, "weight": body.weight}
