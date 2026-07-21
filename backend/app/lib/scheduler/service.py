"""Background-services orchestration — port of src/lib/server/background-services.ts.

Replaces Node's three ``setInterval``/``setTimeout`` loops with a single
``AsyncIOScheduler`` running on FastAPI's event loop:

  * RSS refresh    — 5s after startup, then every 15 minutes
  * Summarization  — 10s after startup, then every 3 minutes
  * Daily backup   — an immediate startup backup, then 3 AM local time daily

Every job is registered with ``max_instances=1`` + ``coalesce=True`` so a slow
run never piles up on the next tick — the run-once-per-tick guarantee Node got
from its single thread. ``start_background_services`` is idempotent per process,
mirroring the ``__newsixityBackgroundServicesStarted`` global flag.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.lib.scheduler.backup import create_daily_backup
from app.lib.scheduler.refresh import refresh_all_feeds
from app.lib.scheduler.summarizer import check_and_summarize

logger = logging.getLogger("newsixity")

RSS_REFRESH_INTERVAL_MINUTES = 15
SUMMARIZE_INTERVAL_MINUTES = 3
BACKUP_HOUR = 3  # 3 AM local time, matching backup/scheduler.ts.

_scheduler: AsyncIOScheduler | None = None
_started = False


def start_background_services() -> AsyncIOScheduler | None:
    """Start the RSS/summarization/backup jobs. Idempotent per process.

    Must be called from within the running event loop (the FastAPI lifespan),
    since ``AsyncIOScheduler`` binds to the current loop.
    """
    global _scheduler, _started
    if _started:
        return _scheduler
    _started = True

    scheduler = AsyncIOScheduler()
    now = datetime.now()

    # RSS refresh: first run 5s after startup (let the app settle), then 15 min.
    scheduler.add_job(
        refresh_all_feeds,
        trigger="interval",
        minutes=RSS_REFRESH_INTERVAL_MINUTES,
        next_run_time=now + timedelta(seconds=5),
        id="rss-refresh",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=None,
    )

    # Summarization: first run 10s after startup, then every 3 min.
    scheduler.add_job(
        check_and_summarize,
        trigger="interval",
        minutes=SUMMARIZE_INTERVAL_MINUTES,
        next_run_time=now + timedelta(seconds=10),
        id="summarize",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=None,
    )

    # Daily backup at 3 AM local time.
    scheduler.add_job(
        create_daily_backup,
        trigger=CronTrigger(hour=BACKUP_HOUR, minute=0),
        id="daily-backup",
        max_instances=1,
        coalesce=True,
    )
    # Plus an immediate backup on startup (matches backup/scheduler.ts).
    scheduler.add_job(
        create_daily_backup,
        trigger="date",
        run_date=now + timedelta(seconds=2),
        id="startup-backup",
        max_instances=1,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "[Newsixity] Background services started (RSS %dm, summarize %dm, backup %02d:00)",
        RSS_REFRESH_INTERVAL_MINUTES,
        SUMMARIZE_INTERVAL_MINUTES,
        BACKUP_HOUR,
    )
    return scheduler


def stop_background_services() -> None:
    """Shut the scheduler down (called on FastAPI lifespan shutdown)."""
    global _scheduler, _started
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
    _started = False
    logger.info("[Newsixity] Background services stopped")
