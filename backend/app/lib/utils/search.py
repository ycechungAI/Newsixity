"""Search engine detection — port of src/lib/utils/search.ts."""

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, parse_qs, unquote


@dataclass
class SearchEngineInfo:
    name: str
    query_param: str
    domain: str


SEARCH_ENGINES = {
    "google": SearchEngineInfo("Google", "q", "google.com"),
    "bing": SearchEngineInfo("Bing", "q", "bing.com"),
    "duckduckgo": SearchEngineInfo("DuckDuckGo", "q", "duckduckgo.com"),
    "yahoo": SearchEngineInfo("Yahoo", "p", "search.yahoo.com"),
    "baidu": SearchEngineInfo("Baidu", "wd", "baidu.com"),
    "yandex": SearchEngineInfo("Yandex", "text", "yandex.com"),
}


@dataclass
class DetectedSearchEngine:
    engine: SearchEngineInfo
    query: str


def detect_search_engine(url: str) -> Optional[DetectedSearchEngine]:
    """Detect if a URL is from a search engine and extract the query."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname.lower() if parsed.hostname else ""

        for engine in SEARCH_ENGINES.values():
            if engine.domain in hostname:
                params = parse_qs(parsed.query)
                query_list = params.get(engine.query_param)
                if query_list:
                    query = unquote(query_list[0])
                    return DetectedSearchEngine(engine, query)

        return None
    except Exception:
        return None


def is_search_engine_url(url: str) -> bool:
    """Check if a URL is a search engine URL."""
    return detect_search_engine(url) is not None
