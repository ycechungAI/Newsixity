"""Engine, session factory, and connection pragmas.

Mirrors the Node setup (``journal_mode = WAL``, ``foreign_keys = ON``). A
``busy_timeout`` is added because, unlike the single-threaded better-sqlite3
process, the Python app touches SQLite from FastAPI's threadpool and the
APScheduler jobs concurrently — the timeout lets writers wait briefly for the
WAL lock instead of erroring with "database is locked".
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.lib.backup.restore import apply_pending_restore

# Must run before _build_engine(): this module is the only guaranteed choke
# point both the dev (`uvicorn app.main:app`) and frozen (`run_server.py`)
# entrypoints pass through to reach the DB, and `engine`/`SessionLocal` below
# are module-level singletons created at import time. Swapping a staged
# restore in after the engine exists would risk touching a live connection;
# doing it here, before anything opens the DB, keeps the swap safe. Defensive
# by design — see apply_pending_restore's docstring for why a failure here
# must never block startup.
apply_pending_restore()


def _build_engine() -> Engine:
    db_path = settings.resolve_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        f"sqlite:///{db_path}",
        # Sessions cross threads (threadpool handlers + scheduler jobs).
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA busy_timeout = 5000")
        cursor.close()

    return engine


engine = _build_engine()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a session that is always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reclaim_space(db: Session) -> None:
    """Return freed pages from recent deletes to the OS immediately.

    Requires ``auto_vacuum = INCREMENTAL`` (set once via the migration that
    converts the DB, see ``scripts/enable_incremental_vacuum.py``). Without it
    this is a harmless no-op — SQLite just keeps freed pages for reuse instead
    of shrinking the file, which is why the DB can grow far past its live
    data size after repeated deletes/prunes.
    """
    db.execute(text("PRAGMA incremental_vacuum"))
    db.commit()
