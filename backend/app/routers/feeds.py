"""Feeds endpoints — /api/feeds/*."""

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.repository import (
    CAPPED_CATEGORIES,
    DuplicateFeedError,
    FeedNotFoundError,
    ProtectedFeedError,
    UnknownCategoryError,
    create_feed,
    delete_feed,
    get_all_feeds,
    update_feed,
    update_feed_source_weight,
)
from app.schemas import (
    Feed,
    FeedCreateRequestBody,
    FeedUpdateRequestBody,
    FeedWeightUpdateRequestBody,
)
from app.lib.integrations import fetch_all_feeds
from app.lib.integrations.rss import probe_feed
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


@router.get(
    "/feeds/weights",
    dependencies=[Depends(rate_limit("feeds-weights-get", 120, TEN_MIN_MS))],
)
async def get_feed_weights() -> dict:
    """Feeds with their ranking weights, for the Settings > Feed Rankings list.

    This had no GET at all: the Settings page requested it, the catch-all
    static route answered with the SPA's index.html at status 200, and the
    JSON parse failed silently — so Feed Rankings rendered empty with no
    error anywhere. A missing API route returning 200 HTML is why that hid.
    """
    feeds = get_all_feeds()
    return {
        "feeds": [
            {
                "id": f.id,
                "name": f.name,
                "url": f.url,
                "enabled": f.enabled,
                "categorySlug": f.category_slug,
                "sourceWeight": f.source_weight,
            }
            for f in feeds
        ]
    }


# PATCH is what the Settings page sends; PUT is kept so any older client
# still works. Registering only PUT meant every weight change 405'd.
# Registered as two routes rather than one api_route(methods=[...]) so each
# gets a distinct OpenAPI operation id instead of colliding.
@router.patch(
    "/feeds/weights",
    operation_id="update_feed_weights",
    dependencies=[Depends(rate_limit("feeds-weights-patch", 60, TEN_MIN_MS))],
)
@router.put(
    "/feeds/weights",
    operation_id="update_feed_weights_put",
    dependencies=[Depends(rate_limit("feeds-weights-patch", 60, TEN_MIN_MS))],
)
async def update_feed_weights(body: FeedWeightUpdateRequestBody) -> dict:
    """Update source weight for a feed."""
    if body.weight < 0.1 or body.weight > 10.0:
        raise HTTPException(status_code=400, detail="Weight must be between 0.1 and 10.0")

    update_feed_source_weight(body.feedId, body.weight)

    return {"success": True, "feedId": body.feedId, "weight": body.weight}


# ── User-managed feeds (v0.4 §1) ──────────────────────────────────────────
# Declared after /feeds/refresh and /feeds/weights so the {feed_id} routes
# can never swallow those literal paths.

_FEED_ERROR_STATUS = {
    FeedNotFoundError: 404,
    ProtectedFeedError: 403,
    DuplicateFeedError: 409,
    UnknownCategoryError: 400,
}


def _feed_http_error(e: Exception) -> HTTPException:
    status = next((s for cls, s in _FEED_ERROR_STATUS.items() if isinstance(e, cls)), 400)
    return HTTPException(status_code=status, detail=str(e))


@router.post(
    "/feeds",
    response_model=Feed,
    status_code=201,
    dependencies=[Depends(rate_limit("feeds-create", 30, TEN_MIN_MS))],
)
async def add_feed(body: FeedCreateRequestBody) -> Feed:
    """Add a user feed after proving it is reachable, safe, and a real feed.

    probe_feed runs the URL (and every redirect hop) through the SSRF gate,
    then requires feedparser to find a title or entries — so a feed that
    would silently never fetch is rejected here, with the reason.
    """
    try:
        probe = await asyncio.to_thread(probe_feed, body.url.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # network errors: timeouts, DNS, HTTP status
        raise HTTPException(status_code=400, detail=f"Could not fetch that URL: {e}") from e

    name = body.name or probe.title or probe.url
    try:
        return create_feed(probe.url, name[:120], body.categorySlug)
    except (DuplicateFeedError, UnknownCategoryError) as e:
        raise _feed_http_error(e) from e


@router.patch(
    "/feeds/{feed_id}",
    response_model=Feed,
    dependencies=[Depends(rate_limit("feeds-update", 120, TEN_MIN_MS))],
)
async def edit_feed(feed_id: int, body: FeedUpdateRequestBody) -> Feed:
    try:
        return update_feed(
            feed_id, name=body.name, enabled=body.enabled, category_slug=body.categorySlug
        )
    except (FeedNotFoundError, ProtectedFeedError, UnknownCategoryError) as e:
        raise _feed_http_error(e) from e


@router.delete(
    "/feeds/{feed_id}",
    dependencies=[Depends(rate_limit("feeds-delete", 60, TEN_MIN_MS))],
)
async def remove_feed(feed_id: int) -> dict:
    """Delete a feed and its unsaved articles; saved ones move to Manual Links."""
    try:
        result = await asyncio.to_thread(delete_feed, feed_id)
    except (FeedNotFoundError, ProtectedFeedError) as e:
        raise _feed_http_error(e) from e
    return {"success": True, **result}
