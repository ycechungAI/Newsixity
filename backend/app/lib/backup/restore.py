"""Backup listing, integrity gate, and staged restore.

Restoring an untrusted SQLite file straight into the live database is the
actual risk here: a hostile ``.db`` file can carry views/triggers/generated
columns that invoke functions the moment something queries it, and a
corrupt file can wedge SQLAlchemy's module-level engine. Two things keep
that risk contained:

1. **Validation gate** (``_validate_sqlite_file``) — every candidate file is
   opened read-only via a ``file:...?mode=ro`` URI, with
   ``PRAGMA trusted_schema=OFF`` set *before* any query, so nothing in the
   file's schema can execute. Then ``integrity_check``, ``foreign_key_check``
   and a ``sqlite_master`` shape check confirm it is actually a Newsixity
   database. The live DB is never touched during validation.
2. **Staged apply** (``apply_pending_restore``) — a validated file is only
   ever moved to ``pending-restore.db`` next to the live DB. The actual swap
   happens at the next process start, from the top of ``app.db.session``,
   before the engine is built — the one choke point both the dev
   (``uvicorn``) and frozen (``run_server.py``) entrypoints share.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import time
import uuid
from pathlib import Path
from urllib.parse import quote

from app.config import settings

logger = logging.getLogger("newsixity")

SQLITE_HEADER = b"SQLite format 3\x00"  # First 16 bytes of every SQLite file.

# Generous but bounded — this is a local single-user desktop DB, not an
# upload service, but we still must not buffer an unbounded body in memory.
MAX_RESTORE_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB

AUTO_PREFIX = "newsixity-auto-"
BACKUP_PREFIX = "newsixity-"
PENDING_RESTORE_NAME = "pending-restore.db"

# Deliberately does NOT start with BACKUP_PREFIX. console.py's
# _cleanup_old_backups() prunes everything matching "newsixity-" down to
# MAX_BACKUPS (2), so a safety copy named "newsixity-pre-restore-..." would
# be deleted by the next couple of manual backups — and that file is the only
# way to undo a restore the user regrets.
SAFETY_PREFIX = "pre-restore-"

# Tables that must exist for a file to be considered a genuine Newsixity DB.
CORE_TABLES = ("articles", "categories", "feeds", "settings")

# Triggers/views Newsixity creates itself, so a normal backup does not get
# flagged. Without this every legitimate restore logs an "unexpected
# triggers" warning (init_db.init_fts5_search adds all three), which trains
# the reader to ignore the one message meant to flag a hostile file.
KNOWN_SCHEMA_OBJECTS = frozenset(
    {"articles_fts_ai", "articles_fts_ad", "articles_fts_au"}
)


class BackupValidationError(Exception):
    """A candidate backup file failed the size/header/integrity/schema gate."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        self.status_code = status_code
        super().__init__(message)


def backups_dir() -> Path:
    d = settings.resolve_db_path().parent / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_backups() -> list[dict]:
    """Enumerate ``*.db`` files in the backups dir (blocking; call via to_thread)."""
    d = backups_dir()
    items: list[dict] = []
    for p in d.iterdir():
        # Skip dotfiles: .DS_Store, and this module's own in-flight temp files
        # (.restore-upload-*.db / .export-*.db), which do end in .db and would
        # otherwise flicker into the list mid-validation.
        if p.suffix != ".db" or p.name.startswith("."):
            continue
        try:
            stat = p.stat()
        except OSError:
            continue
        if p.name.startswith(SAFETY_PREFIX):
            kind = "safety"
        elif p.name.startswith(AUTO_PREFIX):
            kind = "auto"
        else:
            kind = "manual"
        items.append(
            {"name": p.name, "size": stat.st_size, "mtime": stat.st_mtime, "type": kind}
        )
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items


def _safe_backup_path(name: str) -> Path:
    """Resolve ``name`` inside the backups dir, rejecting any path traversal."""
    d = backups_dir()
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        raise BackupValidationError("Invalid backup name")

    candidate = (d / name).resolve()
    resolved_dir = d.resolve()
    if candidate != resolved_dir and resolved_dir not in candidate.parents:
        raise BackupValidationError("Invalid backup name")
    return candidate


def _validate_sqlite_file(path: Path) -> None:
    """Run the full integrity gate against a file already on disk.

    Raises ``BackupValidationError`` on any failure. Never touches the live
    database — opens ``path`` read-only via a URI connection.
    """
    with open(path, "rb") as f:
        header = f.read(16)
    if header != SQLITE_HEADER:
        raise BackupValidationError("Not a valid SQLite database (bad file header)")

    uri = f"file:{quote(path.as_posix())}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as e:
        raise BackupValidationError(f"Could not open database: {e}") from e

    try:
        try:
            # Must run before any other query — stops a hostile file's views,
            # triggers, or generated columns from invoking functions at open time.
            conn.execute("PRAGMA trusted_schema=OFF")

            integrity_rows = conn.execute("PRAGMA integrity_check").fetchall()
            integrity_ok = len(integrity_rows) == 1 and integrity_rows[0][0] == "ok"
            if not integrity_ok:
                raise BackupValidationError("Database failed integrity check")

            fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
            if fk_violations:
                raise BackupValidationError("Database failed foreign key check")

            schema_rows = conn.execute(
                "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view', 'trigger')"
            ).fetchall()
        except sqlite3.Error as e:
            # A malformed (but header-valid) file surfaces as a DatabaseError
            # here, at query time, rather than at connect() time above.
            raise BackupValidationError(f"Database failed integrity check: {e}") from e

        table_names = {name for name, kind in schema_rows if kind == "table"}
        missing = [t for t in CORE_TABLES if t not in table_names]
        if missing:
            raise BackupValidationError(
                "Not a Newsixity database (missing tables: " + ", ".join(missing) + ")"
            )

        unexpected = [
            f"{kind}:{name}"
            for name, kind in schema_rows
            if kind in ("view", "trigger") and name not in KNOWN_SCHEMA_OBJECTS
        ]
        if unexpected:
            logger.warning(
                "[Newsixity] Restore candidate %s has unexpected triggers/views: %s",
                path.name,
                ", ".join(unexpected),
            )
    finally:
        conn.close()


def _stage_validated_file(tmp_path: Path) -> dict:
    """Move an already-validated temp file into the pending-restore slot."""
    db_dir = settings.resolve_db_path().parent
    pending_path = db_dir / PENDING_RESTORE_NAME
    shutil.move(str(tmp_path), str(pending_path))
    logger.info("[Newsixity] Restore staged: %s", pending_path)
    return {"staged": True, "pendingPath": str(pending_path)}


def stage_restore_from_bytes(data: bytes) -> dict:
    """Validate an uploaded raw DB body and stage it for restore on next boot.

    Blocking (file I/O + sqlite3) — call via ``asyncio.to_thread``.
    """
    if len(data) > MAX_RESTORE_UPLOAD_BYTES:
        raise BackupValidationError("Upload too large", status_code=413)
    if len(data) < 16 or data[:16] != SQLITE_HEADER:
        raise BackupValidationError("Not a valid SQLite database (bad file header)")

    d = backups_dir()
    tmp_path = d / f".restore-upload-{uuid.uuid4().hex}.db"
    tmp_path.write_bytes(data)
    try:
        _validate_sqlite_file(tmp_path)
        return _stage_validated_file(tmp_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def stage_restore_from_existing(name: str) -> dict:
    """Validate an existing backup (by name) and stage it for restore on next boot.

    Blocking (file I/O + sqlite3) — call via ``asyncio.to_thread``.
    """
    src = _safe_backup_path(name)
    if not src.is_file():
        raise BackupValidationError("Backup not found", status_code=404)

    size = src.stat().st_size
    if size > MAX_RESTORE_UPLOAD_BYTES:
        raise BackupValidationError("Backup too large", status_code=413)

    d = backups_dir()
    tmp_path = d / f".restore-existing-{uuid.uuid4().hex}.db"
    # Copy rather than validate-in-place: the original backup must remain
    # untouched in the list regardless of what staging does with the copy.
    shutil.copy2(src, tmp_path)
    try:
        _validate_sqlite_file(tmp_path)
        return _stage_validated_file(tmp_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _snapshot_db(src: Path, dest: Path) -> None:
    """Write a consistent single-file snapshot of ``src`` to ``dest``.

    Not shutil.copy2: the database runs in WAL mode, so transactions that are
    committed but not yet checkpointed live in the ``-wal`` sidecar, not in
    the main file. A plain file copy would silently omit them — and
    apply_pending_restore deletes that ``-wal`` moments later, making the loss
    permanent. That is precisely the data this safety copy exists to protect,
    and force-quitting the app (the case where a restore is most likely) is
    exactly when the WAL is non-empty.

    VACUUM INTO folds the WAL into the output, matching what
    ``POST /api/console/backup`` already does for user-initiated backups.
    """
    conn = sqlite3.connect(str(src))
    try:
        # dest is a path we construct ourselves from a strftime timestamp,
        # never user input, so there is nothing to interpolate unsafely here.
        conn.execute("VACUUM INTO ?", (str(dest),))
    finally:
        conn.close()


def resolve_backup_for_download(name: str) -> Path:
    """Resolve an existing backup by name for streaming to the client.

    Path traversal is rejected by ``_safe_backup_path``; this only ever
    serves files that already sit inside the backups directory.
    """
    path = _safe_backup_path(name)
    if not path.is_file() or path.suffix != ".db":
        raise BackupValidationError("Backup not found", status_code=404)
    return path


def export_live_snapshot() -> Path:
    """Snapshot the live DB to a fresh temp file and return its path.

    This is the "export now" path: it does not require the user to create a
    backup first, and unlike copying newsixity.db by hand it captures WAL
    content, so the exported file is a complete, self-contained database that
    the restore endpoint on another machine will accept.

    The caller is responsible for deleting the returned file once it has been
    streamed. Blocking — call via ``asyncio.to_thread``.
    """
    db_path = settings.resolve_db_path()
    if not db_path.is_file():
        raise BackupValidationError("No database to export", status_code=404)

    tmp_path = backups_dir() / f".export-{uuid.uuid4().hex}.db"
    _snapshot_db(db_path, tmp_path)
    # Same gate the import side runs, so a machine can never hand out a file
    # its own restore endpoint would reject.
    _validate_sqlite_file(tmp_path)
    return tmp_path


def export_filename() -> str:
    """Timestamped, machine-neutral name for a downloaded export."""
    ts = time.strftime("%Y-%m-%dT%H-%M-%S", time.gmtime())
    return f"newsixity-export-{ts}.db"


def apply_pending_restore() -> None:
    """Swap a staged restore into place at startup, before the engine is built.

    Defensive by design: this runs at import time of ``app.db.session``, the
    one choke point shared by dev (``uvicorn app.main:app``) and frozen
    (``run_server.py``) entrypoints. Any failure here is logged and swallowed
    — it must never prevent the app from starting.
    """
    try:
        db_path = settings.resolve_db_path()
        db_dir = db_path.parent
        pending_path = db_dir / PENDING_RESTORE_NAME

        if not pending_path.is_file():
            return

        logger.info("[Newsixity] Staged restore found, applying: %s", pending_path)

        if db_path.is_file():
            try:
                backups = db_dir / "backups"
                backups.mkdir(parents=True, exist_ok=True)
                ts = time.strftime("%Y-%m-%dT%H-%M-%S", time.gmtime())
                safety_path = backups / f"{SAFETY_PREFIX}{ts}.db"
                _snapshot_db(db_path, safety_path)
                logger.info("[Newsixity] Safety copy of current DB created: %s", safety_path)
            except Exception as e:  # noqa: BLE001
                logger.error(
                    "[Newsixity] Failed to create safety copy before restore, "
                    "aborting restore to avoid data loss: %s",
                    e,
                )
                return

        # Stale WAL/SHM sidecars from the previous engine must not linger and
        # get replayed against the swapped-in file.
        for base in (db_path, pending_path):
            for suffix in ("-wal", "-shm"):
                sidecar = Path(str(base) + suffix)
                try:
                    sidecar.unlink(missing_ok=True)
                except OSError as e:
                    # Not fatal — a leftover sidecar next to the restored file
                    # is recoverable, and refusing to start over it would be
                    # worse. Log it so an unwritable data dir is still visible.
                    logger.warning(
                        "[Newsixity] Could not remove stale sidecar %s: %s", sidecar, e
                    )

        shutil.move(str(pending_path), str(db_path))
        logger.info("[Newsixity] Restore applied successfully: %s", db_path)
    except Exception as e:  # noqa: BLE001
        logger.error("[Newsixity] apply_pending_restore failed: %s", e)
