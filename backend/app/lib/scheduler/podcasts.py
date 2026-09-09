"""Podcast feed refresh job — re-fetches subscribed podcast feeds on a schedule."""

from __future__ import annotations

import asyncio
import logging

from app.lib.podcast.refresh import refresh_all_podcasts

logger = logging.getLogger("newsixity")


async def refresh_all_podcasts_job() -> None:
    """Scheduled podcast feed refresh. Runs the blocking refresh in a worker thread."""
    try:
        result = await asyncio.to_thread(refresh_all_podcasts)
        logger.info(
            "[Newsixity] Podcast refresh complete: %d/%d feeds updated",
            result["updated_feeds"],
            result["total_feeds"],
        )
    except Exception as e:  # noqa: BLE001
        logger.error("[Newsixity] Podcast refresh error: %s", e)