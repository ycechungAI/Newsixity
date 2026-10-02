"""Federated search providers (v0.4 §2b).

Each provider takes a query and returns a list of RemoteResult, fetched on
the server through the SSRF gate — never from the browser, where CORS blocks
it (that is what killed the old SearchResults.tsx). One provider so far:
Hacker News via the Algolia JSON API — a documented API, so no HTML scraping
to rot and no ToS question.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from urllib.parse import urlencode

from app.lib.integrations.rss import fetch_feed_bytes
from app.lib.utils.url import parse_http_url

REMOTE_TIMEOUT_SECONDS = 5.0
HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
HN_ITEM_URL = "https://news.ycombinator.com/item?id="


@dataclass
class RemoteResult:
    title: str
    url: str
    source: str
    discussionUrl: str | None = None
    points: int | None = None
    comments: int | None = None
    publishedAt: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def search_hacker_news(query: str, limit: int = 10) -> list[RemoteResult]:
    """Stories matching `query`, as ranked by Algolia's HN index."""
    params = urlencode({"query": query, "tags": "story", "hitsPerPage": limit})
    payload = json.loads(fetch_feed_bytes(f"{HN_SEARCH_URL}?{params}", REMOTE_TIMEOUT_SECONDS))

    results: list[RemoteResult] = []
    for hit in payload.get("hits", []):
        title = (hit.get("title") or "").strip()
        object_id = str(hit.get("objectID") or "")
        if not title or not object_id.isdigit():
            continue
        discussion = HN_ITEM_URL + object_id
        # Ask HN / Show HN posts have no outbound URL — link the thread.
        # parse_http_url also drops javascript: and other non-http targets
        # before they can reach an href.
        url = parse_http_url(hit.get("url")) or discussion
        results.append(
            RemoteResult(
                title=title,
                url=url,
                source="Hacker News",
                discussionUrl=discussion,
                points=hit.get("points"),
                comments=hit.get("num_comments"),
                publishedAt=hit.get("created_at"),
            )
        )
    return results


PROVIDERS = {"hackernews": search_hacker_news}
