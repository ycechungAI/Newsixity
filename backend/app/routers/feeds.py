"""Feeds endpoints — /api/feeds/*."""

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.repository import (
    DuplicateFeedError,
    FeedNotFoundError,
    ProtectedFeedError,
    UnknownCategoryError,
    create_feed,
    delete_feed,
    get_all_feeds,
    get_category_by_slug,
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

# Strong references to in-flight fire-and-forget tasks.
#
# asyncio only holds a weak reference to a running task, so an unreferenced
# task can be garbage collected mid-execution and the work simply never
# happens — silently. This is the documented pattern for keeping them alive:
# hold the task here, and drop it from the set once it's done.
_BACKGROUND_TASKS: set[asyncio.Task] = set()


def _run_in_background(coro) -> None:
    """Schedule a coroutine and keep it referenced until it finishes."""
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)


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

    Implements the full algorithm: finance-priority sorting, per-feed daily
    caps with a section-wide fairness floor, exact+fuzzy dedup, quality cut,
    grouping, and promotion. Fires background summarization after completion
    (fire-and-forget).

    The ``caps`` array is the §2.8 report: one entry per feed that had
    something to offer, with ``limit`` naming the cap that held it back
    ("soft"/"hard") or null when it simply had nothing new. Without it a
    silenced feed and a quiet one look identical from outside.
    """
    if category and not get_category_by_slug(category):
        raise HTTPException(
            status_code=400, detail=f"Invalid category: {category}"
        )

    # Run the full refresh algorithm synchronously (blocking in thread pool)
    try:
        outcome = await asyncio.to_thread(_run_feed_refresh_sync, category)
    except Exception as e:
        import logging
        logging.error("[Newsixity] Feed refresh error: %s", e)
        return {"refreshed": 0, "newArticles": 0, "errors": [f"Internal error: {e}"], "caps": []}

    # Fire-and-forget background summarization after refresh completes (matches Node)
    async def fire_summarize():
        try:
            await background_summarize(10)
        except Exception as e:
            import logging
            logging.warning("[Newsixity] Background summarization error: %s", e)

    _run_in_background(fire_summarize())

    return {
        "refreshed": outcome.refreshed,
        "newArticles": outcome.new_articles,
        "errors": outcome.errors,
        "caps": [
            {
                "feedId": c.feed_id,
                "feedName": c.feed_name,
                "categorySlug": c.category_slug,
                "limit": c.limit,
                "stored24h": c.stored_24h,
                "softCap": c.soft_cap,
                "hardCap": c.hard_cap,
            }
            for c in outcome.caps
        ],
    }


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
    """Update source weight for a feed.

    The range is validated in the schema (0.5-2.0 — spec-v0.5 3.1), the same
    range score_article reads, so a stored weight is always the weight that was
    scored. An unknown feedId is a 404 and the protected Manual Links feed is a
    403, both of which the Settings UI now surfaces instead of silently
    showing a change that never landed.
    """
    try:
        update_feed_source_weight(body.feedId, body.weight)
    except (FeedNotFoundError, ProtectedFeedError) as e:
        raise _feed_http_error(e) from e

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
