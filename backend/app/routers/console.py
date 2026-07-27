"""Console (admin) endpoints — /api/console/*.

Port of src/app/api/console/{route,queue,cull,backup,stop,resummarize-failed}.ts.
Gated behind loopback-trust auth wired in Stage 6 — these are local-admin-only
operations (queue management, DB backup, dev-server restart).
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask

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
from app.lib.backup.restore import (
    AUTO_PREFIX,
    MAX_RESTORE_UPLOAD_BYTES,
    BackupValidationError,
    export_filename,
    export_live_snapshot,
    list_backups,
    resolve_backup_for_download,
    stage_restore_from_bytes,
    stage_restore_from_existing,
)
from app.lib.logger.console import get_logs
from app.lib.server.rate_limit import ONE_HOUR_MS, TEN_MIN_MS, rate_limit

logger = logging.getLogger("newsixity")

router = APIRouter()

MAX_BACKUPS = 2


@router.get(
    "/console",
    dependencies=[Depends(rate_limit("console-get", 1000, TEN_MIN_MS))],  # High limit for 500ms refresh rate
)
async def get_console_state() -> dict:
    queue = get_summarization_queue(50)  # Show up to 50 items for better real-time visibility
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


def _cleanup_old_backups(backups_dir: Path, prefix: str, exclude_prefix: str | None = None) -> None:
    """Keep only the MAX_BACKUPS most recent backups starting with ``prefix``.

    ``exclude_prefix`` filters out names that also match a *more specific*
    prefix — e.g. pruning manual backups (prefix ``"newsixity-"``) must not
    also delete automatic ones (prefix ``"newsixity-auto-"``), since every
    auto backup name also starts with ``"newsixity-"``. Bug: this used to be
    called without ``exclude_prefix``, so a manual backup's cleanup could
    delete automatic backups.
    """
    try:
        backups = sorted(
            (
                p
                for p in backups_dir.iterdir()
                if p.name.startswith(prefix)
                and p.suffix == ".db"
                and not (exclude_prefix and p.name.startswith(exclude_prefix))
            ),
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
    _cleanup_old_backups(backups_dir, "newsixity-", exclude_prefix=AUTO_PREFIX)

    total_backups = len(
        [
            p
            for p in backups_dir.iterdir()
            if p.name.startswith("newsixity-")
            and not p.name.startswith(AUTO_PREFIX)
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


@router.get(
    "/console/backups",
    dependencies=[Depends(rate_limit("console-backups-list", 60, TEN_MIN_MS))],
)
async def get_backups() -> dict:
    """List `*.db` files in the backups dir (name, size, mtime, auto/manual)."""
    backups = await asyncio.to_thread(list_backups)
    return {"backups": backups}


@router.get(
    "/console/backups/export",
    dependencies=[Depends(rate_limit("console-backups-export", 10, ONE_HOUR_MS))],
)
async def export_live_database():
    """Download a snapshot of the *current* database, taken on demand.

    "Hot" in the sense that it needs no prior backup and no restart — it
    snapshots the live DB as it is right now. The file that comes back is a
    complete standalone database (VACUUM INTO folds in WAL content, which a
    manual copy of newsixity.db would miss), so it can be carried to another
    machine and fed straight to POST /console/backups/restore there.
    """
    try:
        tmp_path = await asyncio.to_thread(export_live_snapshot)
    except BackupValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=e.status_code)
    except Exception as e:  # noqa: BLE001
        logger.error("[Newsixity] Database export failed: %s", e)
        return JSONResponse({"error": "Export failed"}, status_code=500)

    # The snapshot is a throwaway; delete it once the response has been sent.
    return FileResponse(
        path=tmp_path,
        media_type="application/octet-stream",
        filename=export_filename(),
        background=BackgroundTask(lambda: tmp_path.unlink(missing_ok=True)),
    )


@router.get(
    "/console/backups/download",
    dependencies=[Depends(rate_limit("console-backups-download", 30, ONE_HOUR_MS))],
)
async def download_backup(name: str = Query(...)):
    """Download an existing backup file from the backups directory as-is."""
    try:
        path = await asyncio.to_thread(resolve_backup_for_download, name)
    except BackupValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=e.status_code)

    return FileResponse(
        path=path,
        media_type="application/octet-stream",
        filename=path.name,
    )


@router.post(
    "/console/backups/restore",
    dependencies=[Depends(rate_limit("console-backups-restore", 5, ONE_HOUR_MS))],
)
async def restore_backup(request: Request, name: str | None = Query(default=None)) -> JSONResponse:
    """Stage a restore for the next app start.

    Two input modes, disambiguated by the ``name`` query param:
      - ``?name=<existing-backup>`` restores a file already in the backups dir.
      - no ``name`` + a raw ``application/octet-stream`` body restores an
        uploaded file. Multipart/`UploadFile` is intentionally not used —
        `python-multipart` is not a backend dependency.

    Both paths run the full validation gate (size cap, magic header,
    read-only integrity/foreign-key/schema checks) before anything is staged;
    the live database is never touched by this endpoint. On success the
    validated file is moved to `pending-restore.db`, applied at the next
    process start by `apply_pending_restore()`.
    """
    try:
        if name:
            result = await asyncio.to_thread(stage_restore_from_existing, name)
        else:
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    if int(content_length) > MAX_RESTORE_UPLOAD_BYTES:
                        return JSONResponse({"error": "Upload too large"}, status_code=413)
                except ValueError:
                    pass

            body = await request.body()
            if not body:
                return JSONResponse(
                    {"error": "No backup name or upload body provided"}, status_code=400
                )
            result = await asyncio.to_thread(stage_restore_from_bytes, body)
    except BackupValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=e.status_code)
    except Exception as e:  # noqa: BLE001
        logger.error("[Newsixity] Backup restore failed: %s", e)
        return JSONResponse({"error": "Restore failed"}, status_code=500)

    return JSONResponse(
        {
            "success": True,
            **result,
            "message": "Restore staged — quit and reopen Newsixity to apply.",
        }
    )
