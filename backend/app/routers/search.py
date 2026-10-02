"""Search breadth beyond the local library (v0.4 §2).

  * /search-links   — user-defined outbound search templates, rendered as
                      one-click links on the results page. Stored as a JSON
                      list in the ``search_links`` setting: the list is tiny
                      and user-owned, so it doesn't earn a table.
  * /search/remote  — federated results fetched server-side (see
                      lib/integrations/remote_search.py). Failure degrades to
                      an empty list plus an error string, never a 5xx: the
                      page must still show local results.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator

from app.db.repository import get_setting, set_setting
from app.lib.integrations.remote_search import PROVIDERS
from app.lib.server.rate_limit import TEN_MIN_MS, rate_limit
from app.lib.utils.url import parse_http_url

logger = logging.getLogger("newsixity")

router = APIRouter()

SEARCH_LINKS_KEY = "search_links"
MAX_SEARCH_LINKS = 20

DEFAULT_SEARCH_LINKS = [
    {"name": "Hacker News", "template": "https://hn.algolia.com/?q={q}"},
    {"name": "Google News", "template": "https://news.google.com/search?q={q}"},
    {"name": "DuckDuckGo", "template": "https://duckduckgo.com/?q={q}"},
    {"name": "Wikipedia", "template": "https://en.wikipedia.org/w/index.php?search={q}"},
]


class SearchLink(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    template: str = Field(min_length=1, max_length=500)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        trimmed = " ".join(v.split())
        if not trimmed:
            raise ValueError("Name is required")
        return trimmed

    @field_validator("template")
    @classmethod
    def _template(cls, v: str) -> str:
        v = v.strip()
        if v.count("{q}") != 1:
            raise ValueError("Template must contain {q} exactly once")
        # Validate the URL the template will produce, not the raw template:
        # braces aren't legal in a URL, but the substituted result must be.
        if not parse_http_url(v.replace("{q}", "test")):
            raise ValueError("Template must be an http(s) URL")
        return v


class SearchLinksBody(BaseModel):
    links: list[SearchLink] = Field(max_length=MAX_SEARCH_LINKS)


def _load_links() -> list[dict]:
    raw = get_setting(SEARCH_LINKS_KEY)
    if raw is None:
        return DEFAULT_SEARCH_LINKS
    try:
        return [SearchLink(**item).model_dump() for item in json.loads(raw)]
    except (ValueError, TypeError):
        # A corrupt value must not take the search page down with it.
        logger.warning("[Newsixity] Ignoring unreadable search_links setting")
        return DEFAULT_SEARCH_LINKS


@router.get(
    "/search-links",
    dependencies=[Depends(rate_limit("search-links-get", 240, TEN_MIN_MS))],
)
async def get_search_links() -> dict:
    return {"links": _load_links()}


@router.put(
    "/search-links",
    dependencies=[Depends(rate_limit("search-links-put", 60, TEN_MIN_MS))],
)
async def put_search_links(body: SearchLinksBody) -> dict:
    links = [link.model_dump() for link in body.links]
    set_setting(SEARCH_LINKS_KEY, json.dumps(links))
    return {"links": links}


@router.get(
    "/search/remote",
    dependencies=[Depends(rate_limit("search-remote", 60, TEN_MIN_MS))],
)
async def remote_search(
    q: str = Query(..., min_length=1, max_length=200),
    provider: str = Query("hackernews", pattern="^[a-z]+$"),
) -> dict:
    search = PROVIDERS.get(provider)
    if search is None:
        return {"provider": provider, "results": [], "error": "Unknown provider"}
    try:
        results = await asyncio.to_thread(search, q.strip())
    except Exception as e:  # timeouts, DNS, bad JSON, SSRF refusal
        logger.info("[Newsixity] Remote search (%s) failed: %s", provider, e)
        return {"provider": provider, "results": [], "error": "Remote search is unavailable right now"}
    return {"provider": provider, "results": [r.to_dict() for r in results], "error": None}
