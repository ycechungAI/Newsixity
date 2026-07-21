"""Health check endpoint — /api/health."""

from fastapi import APIRouter

from app.db.repository import get_categories, get_all_feeds
from app.schemas import HealthStatus

router = APIRouter()


@router.get("/health", response_model=HealthStatus)
async def get_health() -> HealthStatus:
    """Get overall system health status."""
    db_healthy = False
    feeds_count = 0
    articles_count = 0
    last_refresh = None

    # Check database
    try:
        categories = get_categories()
        feeds = get_all_feeds()

        db_healthy = len(categories) > 0
        feeds_count = len(feeds)

        # Find most recent lastFetchedAt
        for feed in feeds:
            if feed.last_fetched_at:
                if last_refresh is None or feed.last_fetched_at > last_refresh:
                    last_refresh = feed.last_fetched_at

        # Get article count
        from app.db.session import SessionLocal
        from sqlalchemy import func, select
        from app.db.models import Article as ArticleModel

        with SessionLocal() as db:
            count = db.execute(select(func.count(ArticleModel.id))).scalar() or 0
            articles_count = count
    except Exception:
        pass

    # Check Ollama (deferred to Stage 4 Sonnet integration)
    ollama_healthy = False
    ollama_models = []

    return HealthStatus(
        db=db_healthy,
        ollama=ollama_healthy,
        ollama_models=ollama_models,
        feeds_count=feeds_count,
        articles_count=articles_count,
        last_refresh=last_refresh,
    )
