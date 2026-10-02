"""Daily AI briefing generation (v0.4 §3).

Generated in the background — by the daily cron job or the page's
"Regenerate" button — and cached by date, because Ollama generation is slow
and a past day's briefing never changes. Reading a briefing never generates
one. Everything runs locally through the same Ollama the summarizer uses.

A module-level flag, like the summarizer's ``_background_running``, stops the
cron run and a button press from generating at the same time; the check and
the set have no ``await`` between them, so the event loop makes it atomic.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date as date_cls
from datetime import datetime, time, timedelta, timezone

from app.db.repository import get_briefing, get_briefing_candidates, save_briefing
from app.lib.integrations.ollama import (
    OllamaModelNotFoundError,
    OllamaUnavailableError,
    generate_briefing_text,
    get_default_model,
)

logger = logging.getLogger("newsixity")

MIN_BRIEFING_ARTICLES = 3

_generating: str | None = None  # the date being generated, if any
_last_error: dict[str, str] = {}


def today_local() -> str:
    return date_cls.today().isoformat()


def generating_date() -> str | None:
    return _generating


def last_error(date: str) -> str | None:
    return _last_error.get(date)


def _utc_window(date: str) -> tuple[str, str]:
    """The local calendar day `date` as a [start, end) UTC window, formatted
    like SQLite's datetime('now') so it compares correctly with fetched_at."""
    local_tz = datetime.now().astimezone().tzinfo
    start = datetime.combine(date_cls.fromisoformat(date), time.min, tzinfo=local_tz)
    end = start + timedelta(days=1)
    fmt = "%Y-%m-%d %H:%M:%S"
    return (
        start.astimezone(timezone.utc).strftime(fmt),
        end.astimezone(timezone.utc).strftime(fmt),
    )


def try_claim(date: str) -> bool:
    """Mark `date` as generating, unless a generation is already running.

    Synchronous on purpose: the regenerate route claims before it schedules
    the task, so a GET straight after the POST already reports
    "generating", and two quick clicks can't both start one.
    """
    global _generating
    if _generating is not None:
        return False
    _generating = date
    _last_error.pop(date, None)
    return True


async def generate_daily_briefing(date: str | None = None, force: bool = False) -> str:
    """Generate and store the briefing for `date` (default: today, local).

    Returns a status string — "generated", "exists", "busy", or "failed"
    (the reason is kept for last_error()). Never raises: this runs from the
    scheduler and from a fire-and-forget task, where an exception would
    only end up in a log.
    """
    date = date or today_local()
    if not force and get_briefing(date) is not None:
        return "exists"
    if not try_claim(date):
        return "busy"
    return await run_claimed_generation(date)


async def run_claimed_generation(date: str) -> str:
    """The generation itself; the caller must hold the claim (try_claim)."""
    global _generating
    try:
        since, until = _utc_window(date)
        # 12 articles, at most 3 per category: enough for a full briefing,
        # few enough that a small local model keeps track of them.
        candidates = await asyncio.to_thread(get_briefing_candidates, since, until, 12, 3)
        if len(candidates) < MIN_BRIEFING_ARTICLES:
            _last_error[date] = (
                "Not enough articles from that day yet — refresh feeds and try again."
            )
            return "failed"

        model = await get_default_model()
        content = await generate_briefing_text(
            [{"title": c.title, "text": c.text, "category": c.category_slug} for c in candidates],
            model=model,
        )
        if not content:
            _last_error[date] = "Ollama returned an empty briefing."
            return "failed"

        sources = [
            {"n": i + 1, "articleId": c.id, "title": c.title, "feedName": c.feed_name}
            for i, c in enumerate(candidates)
        ]
        await asyncio.to_thread(save_briefing, date, content, sources, model)
        logger.info("[Newsixity] Daily briefing for %s generated (%d articles)", date, len(candidates))
        return "generated"
    except OllamaUnavailableError:
        _last_error[date] = "Ollama is not running — start it to generate the briefing."
        return "failed"
    except OllamaModelNotFoundError:
        _last_error[date] = "The selected Ollama model isn't installed — pick one in Settings."
        return "failed"
    except Exception as e:  # noqa: BLE001 — never let a briefing crash its caller
        logger.warning("[Newsixity] Daily briefing for %s failed: %s", date, e)
        _last_error[date] = "Briefing generation failed — see the Console for details."
        return "failed"
    finally:
        _generating = None


async def scheduled_daily_briefing() -> None:
    """Cron entry point: today's briefing, unless one already exists."""
    status = await generate_daily_briefing()
    if status == "failed":
        logger.info("[Newsixity] Daily briefing skipped: %s", last_error(today_local()))
