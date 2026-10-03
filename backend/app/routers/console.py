"""Console (admin) endpoints — /api/console/*.

Port of src/app/api/console/{route,queue,cull,backup,stop,resummarize-failed}.ts.
Gated behind loopback-trust auth wired in Stage 6 — these are local-admin-only
operations (queue management, DB backup, dev-server restart).
"""

from __future__ import annotations

import asyncio
import logging
import shutil
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
    set_feed_full_text_blocked,
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
from app.lib.services.backfill import MAX_CONCURRENCY

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


@router.get(
    "/console/full-text-status",
    dependencies=[Depends(rate_limit("console-full-text-status", 60, TEN_MIN_MS))],
)
async def full_text_status() -> dict:
    """How many articles still hold teaser-length text.

    The count is a single aggregate; the sample is a handful of rows for the
    Console to preview. Deliberately not the whole pending set — loading 600+
    rows just to render a number was duplicated effort.
    """
    from app.db.repository import (
        count_articles_needing_full_text,
        get_articles_needing_full_text,
        get_feeds_unable_to_serve_text,
    )
    from app.lib.services.article_text import TEASER_MAX_LENGTH

    pending = await asyncio.to_thread(
        count_articles_needing_full_text, TEASER_MAX_LENGTH
    )
    sample = await asyncio.to_thread(
        get_articles_needing_full_text, TEASER_MAX_LENGTH, 10
    )
    return {
        "pending": pending,
        "threshold": TEASER_MAX_LENGTH,
        "sample": [
            {"id": a.id, "title": a.title[:80], "feed": a.feed_name,
             "length": len(a.content or "")}
            for a in sample
        ],
        "blockedFeeds": await asyncio.to_thread(get_feeds_unable_to_serve_text),
    }


@router.post("/console/full-text-unblock")
async def full_text_unblock(feed_id: int = Query(...)) -> dict:
    """Clear a feed's "can't serve text" mark so it's tried again.

    Blocking is measured, not permanent — a publisher may lift a paywall or a
    bot block, and a stale flag would silently exclude a working source.
    """
    await asyncio.to_thread(set_feed_full_text_blocked, feed_id, None)
    return {"success": True, "feedId": feed_id}


@router.post("/console/backfill-full-text")
async def backfill_full_text_endpoint(
    concurrency: int = Query(
        0, ge=0, le=MAX_CONCURRENCY,
        description="Articles to fetch at once; 0 uses the detected default",
    ),
) -> dict:
    """Start a full-text backfill in the background.

    Runs as a job rather than blocking: the original design fetched one bounded
    batch per request, which meant repairing ~600 articles meant clicking a
    button 60 times. Poll ``/console/backfill-full-text/status`` for progress
    and POST the same path with ``cancel=true`` to stop it.
    """
    from app.lib.services.backfill import (
        DEFAULT_CONCURRENCY,
        get_active_job,
        start_job,
    )

    # One run at a time — a second would duplicate every fetch.
    existing = get_active_job()
    if existing is not None and existing.running:
        return {"success": False, "message": "Already running", **existing.snapshot()}

    job, error = start_job(concurrency or DEFAULT_CONCURRENCY)
    if error:
        return {"success": False, "message": error}

    return {"success": True, **job.snapshot()}


@router.get("/console/backfill-full-text/status")
async def backfill_full_text_status() -> dict:
    """Progress for the running (or last finished) backfill."""
    from app.lib.services.backfill import (
        DEFAULT_CONCURRENCY,
        default_concurrency,
        get_active_job,
    )

    job = get_active_job()
    if job is None:
        return {
            "running": False,
            "processed": 0,
            "repaired": 0,
            "total": 0,
            "percent": 0,
            "concurrency": DEFAULT_CONCURRENCY,
            "suggestedConcurrency": default_concurrency(),
            "maxConcurrency": MAX_CONCURRENCY,
        }
    return {**job.snapshot(), "suggestedConcurrency": default_concurrency(),
            "maxConcurrency": MAX_CONCURRENCY}


@router.post("/console/backfill-full-text/cancel")
async def backfill_full_text_cancel() -> dict:
    """Ask a running backfill to stop. Takes effect at the next batch boundary."""
    from app.lib.services.backfill import get_active_job

    job = get_active_job()
    if job is None or not job.running:
        return {"success": False, "message": "Nothing is running"}
    job.cancel()
    return {"success": True, "message": "Stopping after the current batch", **job.snapshot()}


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


@router.post(
    "/console/backups/export-to-disk",
    dependencies=[Depends(rate_limit("console-backups-export-disk", 10, ONE_HOUR_MS))],
)
async def export_database_to_disk() -> JSONResponse:
    """Write a snapshot to the user's Downloads folder and return the path.

    The streaming download at /console/backups/export works in a browser but
    not in the packaged app: a blob + `<a download>` is a no-op in Tauri's
    WKWebView, so the Export button appeared to do nothing once installed.
    Writing server-side sidesteps the webview entirely — the backend and the
    filesystem are on the same machine for this app, so there is nothing to
    transfer.
    """
    try:
        tmp_path = await asyncio.to_thread(export_live_snapshot)
    except BackupValidationError as e:
        return JSONResponse({"error": str(e)}, status_code=e.status_code)
    except Exception as e:  # noqa: BLE001
        logger.error("[Newsixity] Database export failed: %s", e)
        return JSONResponse({"error": "Export failed"}, status_code=500)

    downloads = Path.home() / "Downloads"
    target_dir = downloads if downloads.is_dir() else Path.home()
    target = target_dir / export_filename()

    try:
        await asyncio.to_thread(shutil.move, str(tmp_path), str(target))
    except Exception as e:  # noqa: BLE001
        tmp_path.unlink(missing_ok=True)
        logger.error("[Newsixity] Could not write export to %s: %s", target, e)
        return JSONResponse(
            {"error": f"Could not write to {target_dir}: {e}"}, status_code=500
        )

    return JSONResponse(
        {
            "success": True,
            "path": str(target),
            "size": target.stat().st_size,
            "message": f"Database exported to {target}",
        }
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
