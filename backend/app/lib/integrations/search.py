"""Search result extraction from search engine URLs — port of src/lib/server/search-extractor.ts.

Uses DuckDuckGo's HTML endpoint since Google/Bing render with JavaScript.
"""

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import httpx

from app.lib.utils.search import detect_search_engine

FETCH_TIMEOUT = 10.0


@dataclass
class ExtractedSearchResult:
    """Single search result extracted from search engine."""
    title: str
    url: str
    description: Optional[str] = None


def parse_duckduckgo_results(html: str) -> list[ExtractedSearchResult]:
    """Parse DuckDuckGo HTML results page."""
    results: list[ExtractedSearchResult] = []
    seen_urls: set[str] = set()

    # Match result blocks: <a class="result__a" href="...">title</a>
    pattern = r'<a[^>]+class=["\']result__a["\'][^>]+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>'

    for match in re.finditer(pattern, html, re.IGNORECASE):
        if len(results) >= 10:
            break

        raw_href = match.group(1)
        title = match.group(2).strip()

        if not title or len(title) < 3:
            continue

        # Extract actual URL from DuckDuckGo redirect
        actual_url = raw_href
        uddg_match = re.search(r"uddg=([^&]+)", raw_href)
        if uddg_match:
            try:
                from urllib.parse import unquote

                actual_url = unquote(uddg_match.group(1))
            except Exception:
                continue

        # Must be a real http(s) URL, skip DDG ad redirects
        if not (actual_url.startswith("http://") or actual_url.startswith("https://")):
            continue

        if "duckduckgo.com/y.js" in actual_url or "bing.com/aclick" in actual_url:
            continue

        # Skip duplicates
        if actual_url in seen_urls:
            continue

        seen_urls.add(actual_url)

        # Extract description if available
        description: Optional[str] = None
        snippet_start = max(0, match.start())
        snippet_end = min(len(html), match.end() + 1000)
        snippet_section = html[snippet_start:snippet_end]

        snippet_match = re.search(
            r'class=["\']result__snippet["\'][^>]*>([^<]+)<', snippet_section
        )
        if snippet_match:
            description = snippet_match.group(1).strip()

        results.append(
            ExtractedSearchResult(title=title, url=actual_url, description=description)
        )

    return results


async def extract_search_results(url: str) -> list[ExtractedSearchResult]:
    """Extract search results from a search engine URL using DuckDuckGo HTML endpoint."""
    search_info = detect_search_engine(url)
    if not search_info:
        return []

    try:
        # Use DuckDuckGo HTML endpoint
        ddg_url = f"https://html.duckduckgo.com/html/?q={quote(search_info.query)}"

        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT) as client:
            response = await client.get(
                ddg_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                },
            )

            if response.status_code != 200:
                return []

            html = response.text
            results = parse_duckduckgo_results(html)
            return results[:5]

    except Exception:
        return []
