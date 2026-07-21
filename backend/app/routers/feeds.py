"""Feeds endpoints — /api/feeds/*."""

from fastapi import APIRouter, Depends, HTTPException

from app.db.repository import get_all_feeds, update_feed_source_weight
from app.schemas import Feed, FeedWeightUpdateRequestBody
from app.lib.integrations import fetch_all_feeds
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
async def refresh_feeds() -> dict:
    """Trigger RSS feed refresh (async background job).

    Stage 7: This will be wired to APScheduler for true background execution.
    For now, a fire-and-forget coroutine.
    """
    # Async RSS fetch (Stage 7: integrated into background scheduler)
    import asyncio

    async def background_refresh():
        try:
            results = await fetch_all_feeds()
            # Process articles and upsert to DB (Stage 5 continuation)
            # For now, just return results
            return {"refreshed": len([r for r in results if not r.error])}
        except Exception as e:
            return {"error": str(e)}

    # Fire-and-forget (Stage 7: proper scheduler integration)
    asyncio.create_task(background_refresh())

    return {"status": "refresh started"}


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
