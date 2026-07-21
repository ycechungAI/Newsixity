"""Article summarization orchestration — port of src/lib/services/SummarizationService.ts."""

from __future__ import annotations

from dataclasses import dataclass

from app.db.repository.helpers import Article
from app.lib.integrations.ollama import OllamaModelNotFoundError, summarize_article

DEFAULT_MODEL = "granite4.1:8b"
BACKUP_MODEL = "llama3.2"


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


async def summarize(title: str, content: str, model: str = DEFAULT_MODEL) -> str:
    """Summarize with the given model, falling back to BACKUP_MODEL if it's not installed."""
    try:
        return await summarize_article(title, content, model)
    except OllamaModelNotFoundError:
        return await summarize_article(title, content, BACKUP_MODEL)


async def process_batch(candidates: list[Article]) -> BatchResult:
    successful = 0
    failed: list[FailedArticle] = []

    for article in candidates:
        if not article.content or len(article.content) < 10:
            failed.append(FailedArticle(article.id, "Article has no sufficient content."))
            continue

        try:
            summary = await summarize(article.title, article.content)
            from app.db.repository import update_article_summary

            update_article_summary(article.id, summary, DEFAULT_MODEL)
            successful += 1
        except SessionLimitExceededError:
            raise
        except Exception as e:
            failed.append(FailedArticle(article.id, f"Transient failure during summarization: {e}"))

    return BatchResult(summarized_count=successful, failed_articles=failed)
