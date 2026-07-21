"""RSS feed configuration + seeding (port of src/lib/rss/feeds.ts)."""

from app.lib.rss.feeds import DEFAULT_FEEDS, seed_all_feeds

__all__ = ["DEFAULT_FEEDS", "seed_all_feeds"]
