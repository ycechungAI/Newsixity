"""Engine, session factory, and connection pragmas.

Mirrors the Node setup (``journal_mode = WAL``, ``foreign_keys = ON``). A
``busy_timeout`` is added because, unlike the single-threaded better-sqlite3
process, the Python app touches SQLite from FastAPI's threadpool and the
APScheduler jobs concurrently — the timeout lets writers wait briefly for the
WAL lock instead of erroring with "database is locked".
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


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
