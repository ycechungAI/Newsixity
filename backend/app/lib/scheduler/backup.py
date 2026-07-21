"""Daily database backup job — port of src/lib/backup/scheduler.ts.

Creates a clean SQLite snapshot via ``VACUUM INTO`` under data/backups with the
``newsixity-auto-`` prefix, keeping only the 10 most recent. The blocking VACUUM
runs in a worker thread so the event loop is never stalled. Scheduling (3 AM
daily + an immediate startup backup) is handled by the APScheduler service.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings

logger = logging.getLogger("newsixity")

MAX_BACKUPS = 10
AUTO_PREFIX = "newsixity-auto-"


def _cleanup_old_backups(backups_dir: Path, prefix: str) -> None:
    """Keep only the MAX_BACKUPS most recent backups with the given prefix."""
    try:
        backups = sorted(
            (
                p
                for p in backups_dir.iterdir()
                if p.name.startswith(prefix) and p.suffix == ".db"
            ),
            key=lambda p: p.stat().st_mtime,
            reverse=True,  # Newest first.
        )
        to_delete = backups[MAX_BACKUPS:]
        for backup in to_delete:
            backup.unlink()
            logger.info("[Newsixity] Deleted old backup: %s", backup.name)
        if to_delete:
            logger.info(
                "[Newsixity] Cleaned up %d old backup(s), kept %d most recent",
                len(to_delete),
                MAX_BACKUPS,
            )
    except Exception as e:  # noqa: BLE001
        logger.error("[Newsixity] Backup cleanup failed: %s", e)


def _create_daily_backup_sync() -> None:
    """Create one auto backup (blocking) and prune old ones."""
    try:
        db_path = settings.resolve_db_path()
        backups_dir = db_path.parent / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        backup_path = backups_dir / f"{AUTO_PREFIX}{timestamp}.db"

        # Clean snapshot via VACUUM INTO (cannot run inside a transaction, so a
        # raw sqlite3 connection is used rather than the ORM session).
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute(f"VACUUM INTO '{backup_path}'")
        finally:
            conn.close()

        size_kb = backup_path.stat().st_size / 1024
        logger.info(
            "[Newsixity] Auto backup created: %s (%.2f KB)", backup_path, size_kb
        )

        _cleanup_old_backups(backups_dir, AUTO_PREFIX)

        total_backups = len(
            [
                p
                for p in backups_dir.iterdir()
                if p.name.startswith(AUTO_PREFIX) and p.suffix == ".db"
            ]
        )
        logger.info("[Newsixity] Total automatic backups: %d", total_backups)
    except Exception as e:  # noqa: BLE001
        logger.error("[Newsixity] Auto backup failed: %s", e)


async def create_daily_backup() -> None:
    """Async entry point for the backup scheduler job."""
    await asyncio.to_thread(_create_daily_backup_sync)
