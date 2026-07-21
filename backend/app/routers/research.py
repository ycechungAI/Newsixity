"""Research endpoints — /api/research, /api/research/history.

Port of src/app/api/research/route.ts and src/app/api/research/history/route.ts.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.lib.server.rate_limit import TEN_MIN_MS, rate_limit
from app.db.repository import (
    delete_article_research,
    get_all_article_research,
    get_article_by_id,
    get_article_research,
    get_remaining_quota,
    get_setting,
    increment_quota,
    is_quota_exceeded,
    save_article_research,
)
from app.lib.integrations import OllamaUnavailableError
from app.lib.research.orchestrator import conduct_research
from app.schemas import ResearchRequestBody

router = APIRouter()


@router.post(
    "/research",
    dependencies=[Depends(rate_limit("research", 30, TEN_MIN_MS))],
)
async def create_research(body: ResearchRequestBody) -> dict:
    normalized_question = body.question.strip()

    article = get_article_by_id(body.articleId)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Check cache first (cached results don't count against quota)
    cached = get_article_research(body.articleId, normalized_question)
    if cached:
        return {"answer": cached.answer, "sources": cached.sources, "cached": True}

    if is_quota_exceeded():
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Monthly research quota reached. The limit will reset next month.",
                "quotaExceeded": True,
            },
        )

    api_key = get_setting("brave_search_api_key")
    ollama_model = get_setting("ollama_model") or "llama3.2"

    try:
        result = await conduct_research(
            article.title, article.content, normalized_question, ollama_model, api_key
        )
    except OllamaUnavailableError:
        raise HTTPException(
            status_code=503,
            detail="Ollama is not available. Make sure Ollama is running locally.",
        )

    increment_quota()

    save_article_research(
        body.articleId, normalized_question, result["answer"], result["sources"], ollama_model
    )

    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "cached": False,
        "quotaRemaining": get_remaining_quota(),
    }


@router.get(
    "/research/history",
    dependencies=[Depends(rate_limit("research-history-get", 120, TEN_MIN_MS))],
)
async def get_research_history(articleId: int = Query(..., gt=0)) -> dict:
    history = get_all_article_research(articleId)
    return {
        "history": [
            {
                "id": item.id,
                "question": item.question,
                "answer": item.answer,
                "sources": item.sources,
                "createdAt": item.created_at,
            }
            for item in history
        ]
    }


@router.delete(
    "/research/history",
    dependencies=[Depends(rate_limit("research-history-delete", 120, TEN_MIN_MS))],
)
async def delete_research_history(id: int = Query(..., gt=0)) -> dict:
    delete_article_research(id)
    return {"success": True, "message": "Research deleted successfully"}
