"""Background-services orchestration — port of src/lib/server/background-services.ts.

Replaces Node's three ``setInterval``/``setTimeout`` loops with a single
``AsyncIOScheduler`` running on FastAPI's event loop:

  * RSS refresh    — 5s after startup, then every 15 minutes
  * Summarization  — 10s after startup, then every 3 minutes
  * Daily backup   — an immediate startup backup, then 3 AM local time daily
  * Daily briefing — 7 AM local time (v0.4 §3)
  * Weather        — hourly observation for each saved city (v0.4 §4)

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
from app.lib.scheduler.briefing import scheduled_daily_briefing
from app.lib.scheduler.podcasts import refresh_all_podcasts
from app.lib.scheduler.refresh import refresh_all_feeds
from app.lib.scheduler.summarizer import check_and_summarize
from app.lib.scheduler.weather import record_weather_for_saved_locations

logger = logging.getLogger("newsixity")

RSS_REFRESH_INTERVAL_MINUTES = 15
SUMMARIZE_INTERVAL_MINUTES = 3
PODCAST_REFRESH_INTERVAL_HOURS = 6
WEATHER_INTERVAL_MINUTES = 60
BACKUP_HOUR = 3  # 3 AM local time, matching backup/scheduler.ts.
# Late enough that the overnight refreshes have landed; the page offers a
# regenerate for anything that arrives later.
BRIEFING_HOUR = 7

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

    # Podcast refresh: first run 30s after startup, then every 6 hours.
    scheduler.add_job(
        refresh_all_podcasts,
        trigger="interval",
        hours=PODCAST_REFRESH_INTERVAL_HOURS,
        next_run_time=now + timedelta(seconds=30),
        id="podcast-refresh",
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

    # Weather history: first run 60s after startup, then hourly.
    scheduler.add_job(
        record_weather_for_saved_locations,
        trigger="interval",
        minutes=WEATHER_INTERVAL_MINUTES,
        next_run_time=now + timedelta(seconds=60),
        id="weather-hourly",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=None,
    )

    # Daily AI briefing at 7 AM local time. A machine asleep at 7 catches up
    # on wake (misfire grace) instead of skipping the day.
    scheduler.add_job(
        scheduled_daily_briefing,
        trigger=CronTrigger(hour=BRIEFING_HOUR, minute=0),
        id="daily-briefing",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=6 * 3600,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "[Newsixity] Background services started (RSS %dm, summarize %dm, podcasts %dh, backup %02d:00, briefing %02d:00)",
        RSS_REFRESH_INTERVAL_MINUTES,
        SUMMARIZE_INTERVAL_MINUTES,
        PODCAST_REFRESH_INTERVAL_HOURS,
        BACKUP_HOUR,
        BRIEFING_HOUR,
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
