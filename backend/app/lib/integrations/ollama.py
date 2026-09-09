"""Ollama LLM integration — port of src/lib/ollama/{client,research}.ts + prompts.ts.

Uses the official `ollama` Python package's AsyncClient. A single in-process
asyncio.Lock replaces the JS enqueue()/processQueue() mutex so only one
summarization/chat call runs at a time (matches the Node app's single-flight
behavior against local Ollama).
"""

from __future__ import annotations

import asyncio

from app.db.repository import get_ollama_model_setting, get_setting

try:
    from ollama import AsyncClient
except ImportError:  # ollama not installed — app must still run (skips summarization)
    AsyncClient = None  # type: ignore[assignment,misc]

OLLAMA_INSTALLED = AsyncClient is not None

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_RESEARCH_MODEL = "llama3.2"
BACKUP_MODEL = "llama3.2:3b"
MAX_CONTENT_LENGTH = 3000
MAX_RESEARCH_ARTICLE_LENGTH = 1500

_cached_default_model: str | None = None

SUMMARIZATION_SYSTEM_PROMPT = (
    'You are a news summarizer. Given a news article title and content, produce a '
    'concise 2-3 sentence summary that captures the key facts. Be neutral and '
    'factual. Do not include opinions or commentary. Do not start with "This '
    'article" or "The article discusses".'
)

GROUP_LABEL_SYSTEM_PROMPT = (
    "Given a list of related news article headlines, generate a short topic label "
    "(3-7 words) that describes the common story or event. Return only the label, "
    "nothing else."
)

RESEARCH_SYSTEM_PROMPT = """You are a research assistant. Your job is to answer questions using ONLY the provided source materials. Follow these rules strictly:

1. Answer ONLY based on information found in the provided sources
2. Cite sources by number like [1], [2], etc.
3. If the sources do not contain enough information to answer the question, say "I don't have enough information from the available sources to answer this question."
4. Be concise and factual
5. Do not speculate or add information not found in the sources
6. If sources conflict, note the disagreement and cite both sides"""


class OllamaUnavailableError(Exception):
    pass


class OllamaModelNotFoundError(Exception):
    pass


def _client(host: str) -> AsyncClient:
    """Return a client, or raise the same error callers already handle for
    unreachable Ollama when the `ollama` package isn't installed."""
    if not OLLAMA_INSTALLED:
        raise OllamaUnavailableError(
            "The 'ollama' package is not installed; Ollama summarization is disabled"
        )
    return AsyncClient(host=host)


def _get_host() -> str:
    return get_setting("ollama_host") or DEFAULT_HOST


def _is_connection_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "connection" in message or "connect" in message or "refused" in message


_summarize_lock = asyncio.Lock()


async def is_ollama_available(host: str | None = None) -> bool:
    if not OLLAMA_INSTALLED:
        return False
    try:
        await _client(host=host or _get_host()).list()
        return True
    except Exception:
        return False


async def get_available_models(host: str | None = None) -> list[str]:
    if not OLLAMA_INSTALLED:
        return []
    try:
        response = await _client(host=host or _get_host()).list()
        return [m.model for m in response.models if m.model]
    except Exception:
        return []


async def get_default_model() -> str:
    """Resolve the model to summarize with: the stored setting if it's an
    installed model, else the first installed model, else BACKUP_MODEL.

    Caches the result so repeated calls (one per article in a batch) don't
    each re-query Ollama's /api/tags.
    """
    global _cached_default_model
    if _cached_default_model:
        return _cached_default_model

    try:
        available = await get_available_models()
    except Exception:
        available = []

    stored = get_ollama_model_setting()
    if stored and stored in available:
        _cached_default_model = stored
        return stored

    if available:
        _cached_default_model = available[0]
        return available[0]

    return BACKUP_MODEL


def invalidate_default_model_cache() -> None:
    """Force the next get_default_model() call to re-resolve from Ollama.

    Call after the user changes the ollama_model setting, so the change
    takes effect immediately instead of waiting for a process restart.
    """
    global _cached_default_model
    _cached_default_model = None


async def summarize_article(title: str, content: str, model: str | None = None) -> str:
    """Summarize a single article, single-flight via a shared lock (matches Node's mutex)."""
    model_to_use = model
    if model_to_use is None:
        model_to_use = await get_default_model()

    truncated_content = content[:MAX_CONTENT_LENGTH]

    async with _summarize_lock:
        try:
            response = await _client(host=_get_host()).chat(
                model=model_to_use,
                stream=False,
                messages=[
                    {"role": "system", "content": SUMMARIZATION_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Title: {title}\n\nContent: {truncated_content}"},
                ],
                options={"temperature": 0.3, "num_predict": 200},
            )
            return response.message.content or ""
        except Exception as e:
            if "not found" in str(e).lower():
                raise OllamaModelNotFoundError(str(e)) from e
            if _is_connection_error(e):
                raise OllamaUnavailableError(
                    "Lost connection to Ollama during summarization"
                ) from e
            raise


async def generate_group_label(titles: list[str], model: str | None = None) -> str:
    host = _get_host()
    if not await is_ollama_available(host):
        raise OllamaUnavailableError(f"Ollama is not running or not reachable at {host}")

    if model is None:
        model = await get_default_model()

    try:
        response = await _client(host=host).chat(
            model=model,
            stream=False,
            messages=[
                {"role": "system", "content": GROUP_LABEL_SYSTEM_PROMPT},
                {"role": "user", "content": "\n".join(titles)},
            ],
            options={"temperature": 0.2, "num_predict": 30},
        )
        return (response.message.content or "").strip()
    except Exception as e:
        if _is_connection_error(e):
            raise OllamaUnavailableError("Lost connection to Ollama during label generation") from e
        raise


async def answer_research_question(
    question: str,
    article_title: str,
    article_content: str | None,
    sources: list[dict],
    model: str = DEFAULT_RESEARCH_MODEL,
) -> str:
    host = _get_host()
    if not await is_ollama_available(host):
        raise OllamaUnavailableError(f"Ollama is not running or not reachable at {host}")

    source_context = "\n\n".join(
        f"[{i + 1}] {s['title']}\nURL: {s['url']}\n{s['snippet']}" for i, s in enumerate(sources)
    )

    if article_content:
        article_context = f'Article: "{article_title}"\n{article_content[:MAX_RESEARCH_ARTICLE_LENGTH]}'
    else:
        article_context = f'Article: "{article_title}"'

    user_prompt = f"""{article_context}

---

Research Sources:
{source_context or "(No sources available)"}

---

Question: {question}"""

    try:
        response = await _client(host=host).chat(
            model=model,
            stream=False,
            messages=[
                {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": 0.2, "num_predict": 500},
        )
        return response.message.content or ""
    except Exception as e:
        if _is_connection_error(e):
            raise OllamaUnavailableError("Lost connection to Ollama during research") from e
        raise
