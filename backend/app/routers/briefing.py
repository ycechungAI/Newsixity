"""Daily AI briefing endpoints — /api/briefing (v0.4 §3).

GET never generates: it serves the cached briefing or reports "missing" /
"generating" so the page can render a plain state instead of a spinner that
hangs on a slow or absent Ollama. POST /briefing/regenerate starts generation
in the background and returns at once; the page polls GET.
"""

from __future__ import annotations

import asyncio
from datetime import date as date_cls
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from app.db.repository import get_briefing, list_briefing_dates
from app.lib.scheduler import briefing as briefing_service
from app.lib.server.rate_limit import TEN_MIN_MS, rate_limit

router = APIRouter()

_ISO_DATE = r"^\d{4}-\d{2}-\d{2}$"
# Keeps the fire-and-forget task referenced until it finishes; asyncio only
# holds weak references, so an unreferenced task can be garbage-collected.
_tasks: set[asyncio.Task] = set()


def _resolve_date(value: Optional[str]) -> str:
    if value is None:
        return briefing_service.today_local()
    try:
        parsed = date_cls.fromisoformat(value)
    except ValueError as e:
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD") from e
    if parsed.isoformat() > briefing_service.today_local():
        raise HTTPException(status_code=422, detail="date is in the future")
    return parsed.isoformat()


@router.get(
    "/briefing",
    dependencies=[Depends(rate_limit("briefing-get", 240, TEN_MIN_MS))],
)
async def read_briefing(date: Optional[str] = Query(None, pattern=_ISO_DATE)) -> dict:
    day = _resolve_date(date)
    stored = await asyncio.to_thread(get_briefing, day)
    generating = briefing_service.generating_date() == day
    if stored is None:
        return {
            "date": day,
            "status": "generating" if generating else "missing",
            "content": None,
            "sources": [],
            "model": None,
            "createdAt": None,
            "error": None if generating else briefing_service.last_error(day),
        }
    return {
        "date": day,
        # A stored briefing being regenerated still shows; the flag lets the
        # page say so.
        "status": "generating" if generating else "ready",
        "content": stored.content,
        "sources": stored.sources,
        "model": stored.model,
        "createdAt": stored.created_at,
        "error": None if generating else briefing_service.last_error(day),
    }


@router.get(
    "/briefing/dates",
    dependencies=[Depends(rate_limit("briefing-dates", 120, TEN_MIN_MS))],
)
async def briefing_dates() -> dict:
    return {"dates": await asyncio.to_thread(list_briefing_dates)}


@router.post(
    "/briefing/regenerate",
    dependencies=[Depends(rate_limit("briefing-regenerate", 20, TEN_MIN_MS))],
)
async def regenerate_briefing(date: Optional[str] = Query(None, pattern=_ISO_DATE)) -> JSONResponse:
    day = _resolve_date(date)
    if not briefing_service.try_claim(day):
        return JSONResponse(
            {"status": "busy", "date": briefing_service.generating_date()}, status_code=409
        )
    task = asyncio.create_task(briefing_service.run_claimed_generation(day))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return JSONResponse({"status": "generating", "date": day}, status_code=202)
