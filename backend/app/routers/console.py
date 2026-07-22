"""Console (admin) endpoints — /api/console/*.

Port of src/app/api/console/{route,queue,cull,backup,stop,resummarize-failed}.ts.
Gated behind loopback-trust auth wired in Stage 6 — these are local-admin-only
operations (queue management, DB backup, dev-server restart).
"""

from __future__ import annotations

import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Query

from app.config import settings
from app.db.repository import (
    cull_unsummarized_queue_to_limit,
    cleanup_unsummarizable_articles,
    get_summarization_queue,
    get_summarization_queue_count,
    remove_article_from_queue,
    reset_failed_and_skipped_articles,
    MAX_UNSUMMARIZED_QUEUE,
)
from app.lib.logger.console import get_logs
from app.lib.server.rate_limit import ONE_HOUR_MS, TEN_MIN_MS, rate_limit

router = APIRouter()

MAX_BACKUPS = 2


@router.get(
    "/console",
    dependencies=[Depends(rate_limit("console-get", 120, TEN_MIN_MS))],
)
async def get_console_state() -> dict:
    queue = get_summarization_queue(20)
    queue_count = get_summarization_queue_count()
    logs = get_logs()

    return {"queue": queue, "queueCount": queue_count, "logs": logs}


@router.delete(
    "/console/queue",
    dependencies=[Depends(rate_limit("console-queue-remove", 100, ONE_HOUR_MS))],
)
async def remove_from_queue(id: int = Query(..., gt=0)) -> dict:
    remove_article_from_queue(id)
    return {"success": True, "removedId": id}


@router.post(
    "/console/cull",
    dependencies=[Depends(rate_limit("console-cull", 10, ONE_HOUR_MS))],
)
async def cull_queue(limit: int = Query(0)) -> dict:
    before = get_summarization_queue_count()
    effective_limit = limit if limit > 0 else MAX_UNSUMMARIZED_QUEUE

    culled = cull_unsummarized_queue_to_limit(effective_limit)
    after = get_summarization_queue_count()

    return {
        "culled": culled,
        "queueCountBefore": before,
        "queueCountAfter": after,
        "limit": effective_limit,
    }


def _cleanup_old_backups(backups_dir: Path, prefix: str) -> None:
    try:
        backups = sorted(
            (p for p in backups_dir.iterdir() if p.name.startswith(prefix) and p.suffix == ".db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for backup in backups[MAX_BACKUPS:]:
            backup.unlink()
    except Exception:
        pass


@router.post(
    "/console/backup",
    dependencies=[Depends(rate_limit("console-backup", 3, ONE_HOUR_MS))],
)
async def create_backup() -> dict:
    backups_dir = settings.resolve_db_path().parent / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    backup_path = backups_dir / f"newsixity-{timestamp}.db"

    conn = sqlite3.connect(str(settings.resolve_db_path()))
    try:
        conn.execute(f"VACUUM INTO '{backup_path}'")
    finally:
        conn.close()

    size_kb = backup_path.stat().st_size / 1024
    _cleanup_old_backups(backups_dir, "newsixity-")

    total_backups = len(
        [
            p
            for p in backups_dir.iterdir()
            if p.name.startswith("newsixity-")
            and not p.name.startswith("newsixity-auto-")
            and p.suffix == ".db"
        ]
    )

    return {
        "success": True,
        "path": str(backup_path),
        "size": f"{size_kb:.2f} KB",
        "timestamp": timestamp,
        "totalBackups": total_backups,
    }


@router.post(
    "/console/stop",
    dependencies=[Depends(rate_limit("console-stop", 20, TEN_MIN_MS))],
)
async def stop_servers() -> dict:
    output_lines: list[str] = []

    for args in (["pkill", "-f", "next dev"], ["pkill", "-x", "ollama"]):
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=10)
            if result.stdout.strip():
                output_lines.append(result.stdout.strip())
        except Exception:
            pass

    return {
        "success": True,
        "message": "Servers stopped successfully",
        "output": "\n".join(output_lines) or "Servers stopped",
    }


@router.post(
    "/console/resummarize-failed",
    dependencies=[Depends(rate_limit("console-resummarize-failed", 10, TEN_MIN_MS))],
)
async def resummarize_failed() -> dict:
    result = reset_failed_and_skipped_articles()
    return {
        "success": True,
        "count": result["count"],
        "message": f"Reset {result['count']} failed/skipped/timed-out articles for resummarization. They will appear in the queue.",
    }


@router.post(
    "/console/cleanup-unsummarizable",
    dependencies=[Depends(rate_limit("console-cleanup", 10, TEN_MIN_MS))],
)
async def cleanup_unsummarizable() -> dict:
    """Delete articles marked as [No content to summarize] - these cannot ever be summarized."""
    result = cleanup_unsummarizable_articles()
    return {
        "success": True,
        "deleted": result["deleted"],
        "message": result["message"],
    }
