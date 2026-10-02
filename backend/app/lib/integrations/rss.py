"""RSS feed parsing and fetching — port of src/lib/rss/parser.ts."""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse

import feedparser
import httpx

from app.lib.integrations.content import resolves_to_blocked_ip
from app.lib.utils.url import parse_http_url

FEED_FETCH_TIMEOUT_SECONDS = 15
FEED_USER_AGENT = "Newsixity/1.0"
MAX_FEED_REDIRECTS = 5
MAX_FEED_BYTES = 10 * 1024 * 1024


class UnsafeFeedUrlError(ValueError):
    """The URL (or a redirect hop) failed the SSRF gate."""


def _check_feed_url(url: str) -> str:
    safe_url = parse_http_url(url)
    if not safe_url:
        raise UnsafeFeedUrlError("Feed URL must be a valid http/https URL")
    if resolves_to_blocked_ip(urlparse(safe_url).hostname):
        raise UnsafeFeedUrlError("Feed URL resolves to a blocked address")
    return safe_url


def _feed_client(timeout: float = FEED_FETCH_TIMEOUT_SECONDS) -> httpx.Client:
    # Redirects are followed by hand in fetch_feed_bytes so each hop is gated.
    return httpx.Client(
        timeout=timeout,
        follow_redirects=False,
        headers={"User-Agent": FEED_USER_AGENT},
    )


def fetch_feed_bytes(url: str, timeout: float = FEED_FETCH_TIMEOUT_SECONDS) -> bytes:
    """GET a feed through the SSRF gate, re-checking every redirect hop.

    Users can add feeds (v0.4), so this is the one place an arbitrary
    outbound address reaches the server. The gate is the same pair
    fetch_podcast_feed uses — parse_http_url() + resolves_to_blocked_ip() —
    but applied per hop: with follow_redirects=True a public URL could
    302 to 127.0.0.1 and the first check would never see it.
    """
    current = _check_feed_url(url)
    with _feed_client(timeout) as client:
        for _ in range(MAX_FEED_REDIRECTS + 1):
            with client.stream("GET", current) as response:
                if response.is_redirect:
                    location = response.headers.get("location", "")
                    current = _check_feed_url(urljoin(current, location))
                    continue
                response.raise_for_status()
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_FEED_BYTES:
                        raise ValueError("Feed is larger than 10 MB")
                    chunks.append(chunk)
                return b"".join(chunks)
    raise ValueError("Too many redirects")


@dataclass
class FeedProbe:
    """What a URL turned out to be when checked before saving it as a feed."""

    url: str
    title: str | None
    entry_count: int


def probe_feed(url: str) -> FeedProbe:
    """Fetch a candidate feed URL and confirm it parses as RSS/Atom.

    Raises ValueError with a user-facing reason otherwise — a feed row that
    silently never fetches is the failure this exists to prevent.
    """
    content = fetch_feed_bytes(url)
    parsed = feedparser.parse(content)
    title = (parsed.get("feed", {}).get("title") or "").strip() or None
    entries = parsed.get("entries", [])
    if not entries and not title:
        raise ValueError("That URL did not return an RSS or Atom feed")
    if parsed.get("bozo") and not entries:
        raise ValueError("The feed could not be parsed")
    return FeedProbe(url=_check_feed_url(url), title=title, entry_count=len(entries))


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
    """Fetch and parse a single RSS feed.

    feedparser.parse() has no timeout parameter, so we fetch the bytes with
    httpx (real connect/read timeout + correct User-Agent) and hand the raw
    content to feedparser. Runs in a worker thread via fetch_all_feeds_sync.
    Goes through the SSRF gate (fetch_feed_bytes) because feed URLs are now
    user-supplied.
    """
    feed_data = feedparser.parse(fetch_feed_bytes(url))

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

    # internal:// feeds (Manual Links) hold user-added articles and have
    # nothing to fetch; trying recorded a bogus last_error every refresh.
    enabled_feeds = [f for f in get_enabled_feeds() if not f.url.startswith("internal://")]

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
