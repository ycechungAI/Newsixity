"""Article summarization orchestration — port of src/lib/services/SummarizationService.ts."""

from __future__ import annotations

from dataclasses import dataclass

from app.db.repository.helpers import Article
from app.lib.integrations.ollama import (
    BACKUP_MODEL,
    OllamaModelNotFoundError,
    get_default_model,
    summarize_article,
)


class SessionLimitExceededError(Exception):
    pass


@dataclass
class FailedArticle:
    id: int
    reason: str


@dataclass
class BatchResult:
    summarized_count: int
    failed_articles: list[FailedArticle]


async def summarize(title: str, content: str, model: str | None = None) -> str:
    """Summarize with the given model (or first available), falling back to BACKUP_MODEL."""
    if not model:
        model = await get_default_model()

    try:
        return await summarize_article(title, content, model)
    except OllamaModelNotFoundError:
        if model != BACKUP_MODEL:
            return await summarize_article(title, content, BACKUP_MODEL)
        raise


async def process_batch(candidates: list[Article]) -> BatchResult:
    successful = 0
    failed: list[FailedArticle] = []
    model_used = await get_default_model()

    for article in candidates:
        if not article.content or len(article.content) < 10:
            failed.append(FailedArticle(article.id, "Article has no sufficient content."))
            continue

        try:
            summary = await summarize(article.title, article.content)
            from app.db.repository import update_article_summary

            update_article_summary(article.id, summary, model_used)
            successful += 1
        except SessionLimitExceededError:
            raise
        except Exception as e:
            failed.append(FailedArticle(article.id, f"Transient failure during summarization: {e}"))

    return BatchResult(summarized_count=successful, failed_articles=failed)
