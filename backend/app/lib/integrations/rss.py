"""RSS feed parsing and fetching — port of src/lib/rss/parser.ts."""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import feedparser


@dataclass
class ParsedArticle:
    """Article extracted from RSS feed."""
    guid: str
    title: str
    link: str
    author: Optional[str]
    published_at: str
    content: Optional[str]
    image_url: Optional[str]


def strip_html(html: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_image_from_html(html: str) -> Optional[str]:
    """Extract first image URL from HTML content."""
    match = re.search(r'<img[^>]+src=["\'](.*?)["\']', html, re.IGNORECASE)
    return match.group(1) if match else None


def fetch_feed(url: str) -> list[ParsedArticle]:
    """Fetch and parse a single RSS feed."""
    feed_data = feedparser.parse(
        url,
        timeout=15,
        response_headers={"User-Agent": "Newsixity/1.0"},
    )

    articles = []
    for entry in feed_data.get("entries", []):
        # Extract GUID
        guid = entry.get("id") or entry.get("link") or entry.get("title") or ""

        # Extract title
        title = (entry.get("title") or "").strip()

        # Extract link
        link = entry.get("link") or ""

        # Extract author (creator > author)
        author = entry.get("author_detail", {}).get("name") if "author_detail" in entry else None
        if not author:
            author = entry.get("author")

        # Extract published date
        published_at = datetime.now().isoformat()
        if entry.get("published"):
            try:
                pub_time = datetime.fromisoformat(entry["published"].replace("Z", "+00:00"))
                published_at = pub_time.isoformat()
            except (ValueError, TypeError):
                pass

        # Extract content with fallback chain
        content = None
        if entry.get("summary"):
            content = entry["summary"][:5000]
        elif entry.get("content"):
            # entry.content is a list of dicts with 'value' key
            content_list = entry.get("content", [])
            if content_list and isinstance(content_list, list):
                content = strip_html(content_list[0].get("value", ""))[:5000]

        # Extract image URL with fallback chain
        image_url = None
        if entry.get("enclosures"):
            # Find first image enclosure
            for enc in entry["enclosures"]:
                if "image" in enc.get("type", ""):
                    image_url = enc.get("href")
                    break

        if not image_url and entry.get("media_content"):
            # Media RSS namespace
            media_list = entry.get("media_content", [])
            if media_list:
                image_url = media_list[0].get("url")

        if not image_url and entry.get("media_thumbnail"):
            # Media thumbnail
            thumb_list = entry.get("media_thumbnail", [])
            if thumb_list:
                image_url = thumb_list[0].get("url")

        if not image_url and entry.get("content"):
            # Extract from HTML content
            content_list = entry.get("content", [])
            if content_list:
                image_url = extract_image_from_html(content_list[0].get("value", ""))

        articles.append(
            ParsedArticle(
                guid=guid,
                title=title,
                link=link,
                author=author,
                published_at=published_at,
                content=content,
                image_url=image_url,
            )
        )

    return articles


@dataclass
class FeedResult:
    """Result from fetching a single feed."""
    feed_id: int
    feed_url: str
    articles: list[ParsedArticle]
    error: Optional[str] = None


def fetch_all_feeds_sync() -> list[FeedResult]:
    """Fetch all enabled feeds (blocking).

    ``feedparser.parse`` performs synchronous network I/O, so the background RSS
    refresh runs this via ``asyncio.to_thread`` to avoid stalling the event loop.
    The async wrapper below preserves the original API for request handlers.
    """
    from app.db.repository.feeds import update_feed_last_fetched, update_feed_last_error
    from app.db.repository import get_enabled_feeds

    enabled_feeds = get_enabled_feeds()

    results: list[FeedResult] = []
    concurrency_limit = 5

    # Process feeds in batches
    for i in range(0, len(enabled_feeds), concurrency_limit):
        batch = enabled_feeds[i : i + concurrency_limit]

        for feed in batch:
            try:
                articles = fetch_feed(feed.url)
                update_feed_last_fetched(feed.id)
                results.append(FeedResult(feed_id=feed.id, feed_url=feed.url, articles=articles))
            except Exception as e:
                error_message = str(e)
                update_feed_last_error(feed.id, error_message)
                results.append(
                    FeedResult(
                        feed_id=feed.id,
                        feed_url=feed.url,
                        articles=[],
                        error=error_message,
                    )
                )

    return results


async def fetch_all_feeds() -> list[FeedResult]:
    """Fetch all enabled feeds, with batch concurrency limit."""
    return fetch_all_feeds_sync()
