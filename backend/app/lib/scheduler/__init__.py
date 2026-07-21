"""Background schedulers (APScheduler) — Stage 7.

Ports src/lib/server/background-services.ts and the RSS / summarization / backup
scheduler modules to a single AsyncIOScheduler on FastAPI's event loop.
"""

from app.lib.scheduler.backup import create_daily_backup
from app.lib.scheduler.refresh import refresh_all_feeds
from app.lib.scheduler.service import (
    start_background_services,
    stop_background_services,
)
from app.lib.scheduler.summarizer import (
    background_summarize,
    check_and_summarize,
    summarize_article_by_id,
)

__all__ = [
    "start_background_services",
    "stop_background_services",
    "refresh_all_feeds",
    "create_daily_backup",
    "background_summarize",
    "check_and_summarize",
    "summarize_article_by_id",
]
