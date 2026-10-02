"""Ask Newsixity endpoint — POST /api/ask.

Perplexity-style Q&A over the local article library (v0.4 "Ask Newsixity"):
retrieve relevant articles with FTS5, synthesize a cited answer with Ollama,
and degrade gracefully when Ollama is offline or nothing matches.

Sessions are ephemeral: the frontend keeps the conversational thread and
sends prior turns back as `history` for follow-up context. No new tables —
nothing here needs to outlive the session.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.db.repository import search_articles
from app.lib.integrations import (
    OllamaModelNotFoundError,
    OllamaUnavailableError,
    answer_research_question,
)
from app.lib.integrations.ollama import get_default_model
from app.lib.server.rate_limit import TEN_MIN_MS, rate_limit
from app.schemas import AskRequestBody

router = APIRouter()

MAX_ASK_SOURCES = 5
MAX_SNIPPET_LENGTH = 1500
MIN_SNIPPET_LENGTH = 20


def _field(item, *names):
    """Read a field from a dict or a dataclass without knowing which one.

    The repository layer mixes both across the port; the Article schema's
    field names (title, link, summary, content, id, ...) are what we match.
    """
    for name in names:
        if isinstance(item, dict):
            value = item.get(name)
        else:
            value = getattr(item, name, None)
        if value is not None:
            return value
    return None


def _to_source(item) -> dict | None:
    """Normalize a search_articles() hit into a citation source.

    Returns None for hits with nothing worth citing (mirrors the orchestrator's
    minimum-snippet rule so the synthesizer never gets empty sources).
    """
    title = _field(item, "title")
    if not title:
        return None
    summary = _field(item, "summary")
    # Placeholder summaries ("[Manual link - not summarizable]", "[Skipped:
    # ...]") are bookkeeping, not content — never feed them to the model.
    if summary and summary.startswith("["):
        summary = None
    snippet = (
        summary
        or (_field(item, "content") or "")[:MAX_SNIPPET_LENGTH]
        or title
    )
    if len(snippet) < MIN_SNIPPET_LENGTH:
        return None
    return {
        "url": _field(item, "link", "url") or "",
        "title": title,
        "snippet": snippet,
        "articleId": _field(item, "id"),
    }


def _to_article_card(item) -> dict:
    """Light article card for the no-synthesis fallback."""
    return {
        "id": _field(item, "id"),
        "title": _field(item, "title"),
        "link": _field(item, "link", "url"),
        "summary": _field(item, "summary"),
        "feedName": _field(item, "feed_name", "feedName"),
        "publishedAt": _field(item, "published_at", "publishedAt"),
    }


def _conversation_context(history) -> str | None:
    """Prior turns for follow-up questions, newest context last."""
    if not history:
        return None
    turns = "\n\n".join(f"Q: {t.question}\nA: {t.answer}" for t in history[-6:])
    return f"Earlier in this conversation:\n{turns}"


@router.post(
    "/ask",
    dependencies=[Depends(rate_limit("ask", 30, TEN_MIN_MS))],
)
async def ask(body: AskRequestBody) -> dict:
    question = body.question.strip()

    # match_any: a question's words are not all in any one article, so
    # AND-ing them ("what" AND "happened" AND ...) would find nothing.
    # A follow-up leans on the previous turn ("what about upscaling on
    # it?"), so retrieve with the previous question's terms as well.
    retrieval_query = question
    if body.history:
        retrieval_query = f"{body.history[-1].question} {question}"
    hits = search_articles(retrieval_query, None, 8, match_any=True) or []
    sources: list[dict] = []
    for hit in hits:
        source = _to_source(hit)
        if source:
            sources.append(source)
        if len(sources) >= MAX_ASK_SOURCES:
            break

    if not sources:
        return {
            "answer": None,
            "sources": [],
            "synthesisAvailable": False,
            "articles": [],
            "message": "No matching articles in your library yet.",
        }

    # The stored setting may name a model that isn't installed; this
    # resolves to one that is (same rule the summarizer uses).
    model = await get_default_model()
    try:
        answer = await answer_research_question(
            question,
            article_title="",
            article_content=None,
            sources=[
                {k: s[k] for k in ("url", "title", "snippet")} for s in sources
            ],
            model=model,
            conversation=_conversation_context(body.history),
        )
    except (OllamaUnavailableError, OllamaModelNotFoundError) as e:
        offline = isinstance(e, OllamaUnavailableError)
        return {
            "answer": None,
            "sources": [],
            "synthesisAvailable": False,
            "articles": [_to_article_card(h) for h in hits[:8]],
            "message": (
                "Ollama is offline — showing matching articles without a synthesized answer."
                if offline
                else f"Ollama has no model '{model}' installed — showing matching articles. "
                "Pick an installed model in Settings."
            ),
        }

    return {
        "answer": answer,
        "sources": sources,
        "synthesisAvailable": True,
        "articles": [],
    }
