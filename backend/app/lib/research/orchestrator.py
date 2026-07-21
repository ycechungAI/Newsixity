"""Deep Research orchestration — port of src/lib/research/orchestrator.ts."""

from __future__ import annotations

import asyncio
from typing import Optional

from app.lib.integrations import answer_research_question, fetch_article_content
from app.lib.research.search import search_web

MAX_SOURCE_LENGTH = 1500
NO_RESULTS_ANSWER = (
    "I don't have enough information from the available sources to answer this "
    "question. The web search returned no results."
)
NO_USABLE_SOURCES_ANSWER = (
    "I don't have enough information from the available sources to answer this "
    "question. Could not extract content from search results."
)


async def _resolve_source(result) -> dict:
    try:
        content = await fetch_article_content(result.url)
        snippet = content[:MAX_SOURCE_LENGTH] if content else result.snippet
    except Exception:
        snippet = result.snippet
    return {"url": result.url, "title": result.title, "snippet": snippet}


async def conduct_research(
    article_title: str,
    article_content: Optional[str],
    question: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> dict:
    search_query = f"{question} {article_title}"
    search_results = await search_web(search_query, max_results=8, api_key=api_key)

    if not search_results:
        return {"answer": NO_RESULTS_ANSWER, "sources": []}

    top_results = search_results[:5]
    sources = await asyncio.gather(*(_resolve_source(r) for r in top_results))
    usable_sources = [s for s in sources if len(s["snippet"]) > 20]

    if not usable_sources:
        return {"answer": NO_USABLE_SOURCES_ANSWER, "sources": []}

    answer = await answer_research_question(
        question, article_title, article_content, usable_sources, model or "llama3.2"
    )

    return {"answer": answer, "sources": usable_sources}
