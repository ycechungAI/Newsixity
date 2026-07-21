"""Web search for the Deep Research feature — port of src/lib/research/search.ts.

Node's fallback path scraped Bing via Playwright when no Brave Search API key
was configured. Stage 4 dropped Playwright (HTTP-only, per spec), so the
fallback here reuses the DuckDuckGo HTML endpoint already wired up for
search-link extraction (app.lib.integrations.search) — no browser required.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import httpx

from app.lib.integrations.search import parse_duckduckgo_results

FETCH_TIMEOUT = 10.0


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str


async def _search_brave(query: str, max_results: int, api_key: str) -> list[SearchResult]:
    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT) as client:
        response = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": max_results},
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
        )
        response.raise_for_status()
        data = response.json()

    results = []
    for item in (data.get("web") or {}).get("results") or []:
        if item.get("url") and item.get("title"):
            results.append(
                SearchResult(
                    url=item["url"],
                    title=item["title"],
                    snippet=item.get("description") or "",
                )
            )
    return results


async def _search_duckduckgo(query: str, max_results: int) -> list[SearchResult]:
    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT) as client:
        response = await client.get(
            f"https://html.duckduckgo.com/html/?q={quote(query)}",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
        )
        if response.status_code != 200:
            return []
        html = response.text

    parsed = parse_duckduckgo_results(html)
    return [
        SearchResult(url=r.url, title=r.title, snippet=r.description or "")
        for r in parsed[:max_results]
    ]


async def search_web(
    query: str, max_results: int = 8, api_key: Optional[str] = None
) -> list[SearchResult]:
    """Search the web using Brave Search API, falling back to DuckDuckGo HTML."""
    search_api_key = api_key or os.environ.get("BRAVE_SEARCH_API_KEY")

    if search_api_key:
        try:
            results = await _search_brave(query, max_results, search_api_key)
            if results:
                return results
        except Exception:
            pass  # Fall through to DuckDuckGo

    try:
        return await _search_duckduckgo(query, max_results)
    except Exception:
        return []
