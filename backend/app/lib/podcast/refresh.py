"""Periodic podcast feed refresh — shared by the scheduler and the /api/podcasts/refresh route."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db.models import PodcastEpisode, PodcastFeed
from app.db.session import SessionLocal
from app.lib.podcast.parser import (
    extract_podcast_episodes,
    fetch_podcast_feed,
)

logger = logging.getLogger("newsixity")


def refresh_all_podcasts() -> dict[str, int]:
    """Re-fetch all subscribed podcast feeds and upsert new episodes.

    Returns ``{"updated_feeds": int, "total_feeds": int}``. Idempotent per
    feed (episodes upsert with ON CONFLICT DO NOTHING), safe to run on a
    schedule as well as on demand.
    """
    with SessionLocal() as session:
        feeds = session.execute(select(PodcastFeed)).scalars().all()
        updated_count = 0

        for feed in feeds:
            try:
                feed_data = fetch_podcast_feed(feed.feed_url)
            except Exception as e:  # noqa: BLE001
                feed.last_error = str(e)
                logger.warning("[Newsixity] Podcast refresh failed for %s: %s", feed.feed_url, e)
                continue

            if feed_data.bozo:
                feed.last_error = "Malformed feed"
                logger.warning("[Newsixity] Podcast feed malformed: %s", feed.feed_url)
                continue

            feed.last_error = None
            episodes = extract_podcast_episodes(feed_data)

            for ep in episodes:
                stmt = (
                    sqlite_insert(PodcastEpisode)
                    .values(podcast_id=feed.id, **ep)
                    .on_conflict_do_nothing()
                )
                session.execute(stmt)
            updated_count += 1

        session.commit()

    return {"updated_feeds": updated_count, "total_feeds": len(feeds)}