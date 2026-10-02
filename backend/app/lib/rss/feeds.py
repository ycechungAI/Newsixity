"""Default RSS feed set + idempotent seeding — port of src/lib/rss/feeds.ts.

``seed_all_feeds`` inserts the default feeds with INSERT-OR-IGNORE semantics
(via the ``seed_feed`` repository helper), so it is safe to call on every RSS
refresh — existing feeds are left untouched and missing categories are skipped
with a warning, matching the Node source.
"""

from __future__ import annotations

import logging

from app.db.repository import seed_feed

logger = logging.getLogger("newsixity")

# slug -> [{"name", "url"}, ...]; identical to DEFAULT_FEEDS in feeds.ts.
DEFAULT_FEEDS: dict[str, list[dict[str, str]]] = {
    "world-news": [
        {"name": "BBC News - World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
        {"name": "BBC News - Top Stories", "url": "https://feeds.bbci.co.uk/news/rss.xml"},
        {"name": "NPR News", "url": "https://feeds.npr.org/1001/rss.xml"},
        {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
        {"name": "Politico", "url": "https://rss.politico.com/politics-news.xml"},
        {"name": "The New Yorker", "url": "https://www.newyorker.com/feed/latest/rss"},
        {"name": "The Register", "url": "https://www.theregister.com/headlines.atom"},
    ],
    "finance": [
        {"name": "MarketWatch - Top Stories", "url": "https://feeds.marketwatch.com/marketwatch/topstories"},
        {"name": "CNBC Top News", "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html"},
        {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex"},
        {"name": "Financial Times", "url": "https://www.ft.com/rss/home"},
        {"name": "Bloomberg", "url": "https://feeds.bloomberg.com/markets/news.rss"},
    ],
    "gaming": [
        {"name": "IGN", "url": "https://feeds.feedburner.com/ign/all"},
        {"name": "Kotaku", "url": "https://kotaku.com/rss"},
        {"name": "PC Gamer", "url": "https://www.pcgamer.com/rss/"},
        {"name": "Eurogamer", "url": "https://www.eurogamer.net/feed"},
        {"name": "Rock Paper Shotgun", "url": "https://www.rockpapershotgun.com/feed"},
        {"name": "GameSpot", "url": "https://www.gamespot.com/feeds/mashup/"},
    ],
    "technology": [
        {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
        {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
        {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index"},
        {"name": "Wired", "url": "https://www.wired.com/feed/rss"},
        {"name": "Engadget", "url": "https://www.engadget.com/rss.xml"},
    ],
    # Device- and platform-specific coverage, split out of technology: these
    # update far more often than the industry feeds above and would otherwise
    # dominate a shared daily insert cap.
    "consumer-tech": [
        {"name": "9to5 Google", "url": "https://9to5google.com/feed/"},
        {"name": "9to5Mac", "url": "https://9to5mac.com/feed/"},
        {"name": "Tom’s Hardware", "url": "https://www.tomshardware.com/feeds/all"},
        {"name": "New Yorker Tech", "url": "https://www.newyorker.com/feed/science/science-and-technology/rss"},
    ],
    "sports": [
        {"name": "ESPN - Top Headlines", "url": "https://www.espn.com/espn/rss/news"},
        {"name": "BBC Sport", "url": "https://feeds.bbci.co.uk/sport/rss.xml"},
        {"name": "CBS Sports", "url": "https://www.cbssports.com/rss/headlines/"},
        {"name": "ESPN Soccer", "url": "https://www.espn.com/espn/rss/soccer/news"},
        {"name": "ESPN Tennis", "url": "https://www.espn.com/espn/rss/tennis/news"},
        {"name": "Sportsnet", "url": "https://www.sportsnet.ca/rss"},
    ],
    "weather": [
        {"name": "Weather.gov Alerts", "url": "https://alerts.weather.gov/cap/us.php?x=1"},
        {"name": "Weather Underground", "url": "https://www.wunderground.com/rss/news.xml"},
        {"name": "AccuWeather", "url": "https://rss.accuweather.com/rss/liveweather_rss.asp?locCode=us"},
        {"name": "Weather.com", "url": "https://weather.com/feeds/enhancedweather"},
    ],
    "top-news": [
        {"name": "AP News - US", "url": "https://rsshub.app/apnews/topics/apf-usnews"},
        {"name": "Reuters - Top News", "url": "https://feeds.reuters.com/reuters/topNews"},
        {"name": "CNN - Top Stories", "url": "https://rss.cnn.com/rss/edition.rss"},
        {"name": "Google News", "url": "https://news.google.com/rss"},
    ],
    # Was seeded separately by init_db, which meant a fresh install and an
    # upgraded one disagreed about what the defaults were. Hacker News is
    # listed here only — it also used to be seeded under technology, which put
    # it in two categories at once.
    "security": [
        {"name": "Data Breaches", "url": "https://databreaches.net/feed/"},
        {"name": "Krebs on Security", "url": "https://krebsonsecurity.com/feed/"},
        {"name": "BleepingComputer", "url": "https://www.bleepingcomputer.com/feed/"},
        {"name": "The Hacker News", "url": "https://feeds.feedburner.com/TheHackersNews"},
        {"name": "Schneier on Security", "url": "https://www.schneier.com/feed/atom/"},
        {"name": "Hacker News", "url": "https://hnrss.org/frontpage"},
    ],
}


def seed_all_feeds() -> None:
    """Insert every default feed (idempotent). Missing categories are skipped."""
    for slug, feeds in DEFAULT_FEEDS.items():
        for feed in feeds:
            try:
                seed_feed(slug, feed["name"], feed["url"])
            except ValueError:
                # Category not present — mirror Node's warn-and-skip.
                logger.warning('Category "%s" not found, skipping feeds', slug)
                break
