"""External API integrations: RSS, content extraction, search."""

from app.lib.integrations.rss import fetch_feed, fetch_all_feeds
from app.lib.integrations.content import fetch_article_content
from app.lib.integrations.search import extract_search_results

__all__ = [
    "fetch_feed",
    "fetch_all_feeds",
    "fetch_article_content",
    "extract_search_results",
]
