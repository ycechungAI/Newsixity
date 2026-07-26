"""Podcast RSS feed parser using feedparser."""

import hashlib
from typing import Any
from urllib.parse import urlparse

import feedparser
import httpx

from app.lib.integrations.content import resolves_to_blocked_ip
from app.lib.utils.url import parse_http_url

FEED_FETCH_TIMEOUT_SECONDS = 15
FEED_USER_AGENT = "Newsixity/1.0"


def fetch_podcast_feed(url: str) -> Any:
    """Fetch and parse a podcast RSS feed, guarding against SSRF.

    Mirrors ``app.lib.integrations.rss.fetch_feed``: fetch bytes with httpx
    (so we control the scheme/host, not feedparser's own URL handling) and
    hand the raw content to feedparser. Raises ValueError if the URL is
    unsafe (non-http(s), credential-bearing, or resolves to a private/
    loopback address).
    """
    safe_url = parse_http_url(url)
    if not safe_url:
        raise ValueError("Feed URL must be a valid http/https URL")

    if resolves_to_blocked_ip(urlparse(safe_url).hostname):
        raise ValueError("Feed URL resolves to a blocked address")

    response = httpx.get(
        safe_url,
        timeout=FEED_FETCH_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={"User-Agent": FEED_USER_AGENT},
    )
    response.raise_for_status()
    return feedparser.parse(response.content)


def parse_duration_seconds(duration_str: str | None) -> int | None:
    """Parse itunes:duration in seconds, hours:minutes:seconds, or minutes:seconds format."""
    if not duration_str:
        return None

    duration_str = duration_str.strip()

    if duration_str.isdigit():
        return int(duration_str)

    parts = duration_str.split(":")
    if len(parts) == 2:
        minutes, seconds = map(int, parts)
        return minutes * 60 + seconds
    elif len(parts) == 3:
        hours, minutes, seconds = map(int, parts)
        return hours * 3600 + minutes * 60 + seconds

    return None


def extract_podcast_feed_info(feed_data: dict[str, Any]) -> dict[str, Any]:
    """Extract podcast feed metadata from feedparser result."""
    feed = feed_data.get("feed", {})
    title = feed.get("title", "Unknown Podcast")
    description = feed.get("summary") or feed.get("description")
    author = feed.get("author")
    site_url = feed.get("link")

    image_url = None
    if "image" in feed:
        image_url = feed["image"].get("href")

    return {
        "title": title,
        "description": description,
        "author": author,
        "site_url": site_url,
        "image_url": image_url,
    }


def extract_podcast_episodes(
    feed_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract episodes from feedparser result, skipping those without audio."""
    episodes = []

    for entry in feed_data.get("entries", []):
        if not entry.get("enclosures"):
            continue

        audio_url = entry["enclosures"][0].get("href")
        if not audio_url:
            continue

        guid = entry.get("id") or entry.get("guid")
        if not guid:
            guid = hashlib.sha256(audio_url.encode()).hexdigest()

        title = entry.get("title", "Untitled")
        published_at = entry.get("published")
        description = entry.get("summary") or entry.get("description")

        duration_seconds = None
        if "itunes_duration" in entry:
            duration_seconds = parse_duration_seconds(entry["itunes_duration"])

        episodes.append(
            {
                "guid": guid,
                "title": title,
                "audio_url": audio_url,
                "duration_seconds": duration_seconds,
                "published_at": published_at,
                "description": description,
            }
        )

    return episodes
