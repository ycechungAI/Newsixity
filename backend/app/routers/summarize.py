"""Summarize endpoint — /api/summarize. Port of src/app/api/summarize/route.ts."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.db.repository import get_article_by_id, get_unsummarized_articles, update_article_summary
from app.lib.services.article_text import ensure_article_text
from app.lib.services.summarization import (
    SessionLimitExceededError,
    process_batch,
    summarize,
)

router = APIRouter()


class SummarizeRequestBody(BaseModel):
    articleId: Optional[int] = None
    model: Optional[str] = None

    model_config = {"populate_by_name": True}


@router.post("/summarize")
async def summarize_endpoint(body: SummarizeRequestBody) -> dict:
    if body.articleId is not None and body.articleId > 0:
        article = get_article_by_id(body.articleId)
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        if article.summary:
            return {"summary": article.summary}

        # Same text-acquisition path as the scheduled queue: if the feed only
        # supplied a teaser, fetch the page. Without this, an article reached
        # via this button summarized from a paragraph while the same article in
        # the queue summarized from the full text.
        text_to_summarize = await ensure_article_text(article)
        if not text_to_summarize or len(text_to_summarize) <= 10:
            raise HTTPException(
                status_code=400, detail="Article has no sufficient content to summarize."
            )

        requested_model = body.model or "llama3.2"

        try:
            summary = await summarize(article.title, text_to_summarize, requested_model)
            update_article_summary(body.articleId, summary, requested_model)
        except Exception:
            raise HTTPException(
                status_code=500, detail="Internal processing failed during single run."
            )

        return {"message": "Single article successfully summarized.", "summary": summary}

    # No articleId provided: batch/resummarization trigger.
    batch_size = settings.get_resummarize_batch_size()
    if batch_size <= 0:
        # Unlimited batch: fetch a very large number (999999) to effectively get all
        articles = get_unsummarized_articles(999999)
    else:
        articles = get_unsummarized_articles(batch_size)

    if not articles:
        return {"message": "No unsummarized articles found for the queue."}

    try:
        result = await process_batch(articles)
        return {
            "message": "Batch processing finished.",
            "summarized": result.summarized_count,
            "errors": [f"ID {f.id}: {f.reason}" for f in result.failed_articles],
        }
    except SessionLimitExceededError:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "External LLM limits are reached.",
                "errors": ["Quota exceeded, manual intervention required."],
            },
        )
    except Exception:
        raise HTTPException(
            status_code=500, detail="A critical server failure occurred during batch execution."
        )
