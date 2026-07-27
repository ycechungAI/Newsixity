"""Schema creation and default seeding — port of the tail of schema.ts.

``create_all`` only creates missing tables, so this is safe to run against the
existing production database. Seeding uses INSERT-OR-IGNORE semantics, matching
the Node ``INSERT OR IGNORE`` calls, so it is idempotent.
"""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.db.base import Base
from app.db.models import Category, Feed
from app.db.session import engine, SessionLocal

logger = logging.getLogger(__name__)

# (name, slug, sort_order) — identical ordering to schema.ts.
DEFAULT_CATEGORIES: list[tuple[str, str, int]] = [
    ("World News", "world-news", 0),
    ("Finance", "finance", 1),
    ("Gaming", "gaming", 2),
    ("Technology", "technology", 3),
    ("Sports", "sports", 4),
    ("Weather", "weather", 5),
    ("Top News", "top-news", 6),
    ("Others", "others", 7),
    ("Security", "security", 9),
]

MANUAL_LINKS_FEED = {"name": "Manual Links", "url": "internal://manual", "enabled": 1}


def _copy_seed_db_if_first_run() -> None:
    """On first launch of a packaged app, copy the bundled seed database.

    In frozen (PyInstaller) mode, a read-only seed database is bundled as
    app data. On first run, copy it to the writable app-data directory so
    the user starts with pre-populated content (465 articles, settings, etc.).
    Subsequent runs reuse the same database (persisting saves, summaries, etc.).
    """
    if not getattr(sys, "frozen", False):
        return  # Dev mode: skip seeding, work directly with repo data/

    db_path = settings.resolve_db_path()
    if db_path.exists():
        return  # DB already exists; not a first run.

    # Find the bundled seed database inside the PyInstaller bundle.
    seed_db = Path(sys._MEIPASS) / "data" / "newsixity.db"  # type: ignore[attr-defined]
    if not seed_db.exists():
        logger.warning("Seed database not found at %s; skipping", seed_db)
        return

    # Copy the seed to the app-data location.
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(seed_db, db_path)
        logger.info("Copied seed database to %s", db_path)
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to copy seed database: %s", e)


def init_fts5_search(session: Session) -> bool:
    """Create the external-content FTS5 search index over articles + triggers.

    ``articles_fts`` mirrors ``title``, ``content``, ``summary`` from
    ``articles`` (``content='articles', content_rowid='id'`` — no duplicated
    storage, the FTS index just references the source table by rowid).
    INSERT/UPDATE/DELETE triggers on ``articles`` keep it in sync going
    forward. Idempotent (``IF NOT EXISTS`` throughout) since this runs on
    every startup against a potentially-existing production database; the
    ``rebuild`` backfill only runs the first time the table is created, not
    on every subsequent startup.

    Not every SQLite build has the FTS5 extension compiled in (notably some
    Windows/Linux CI images) — probe for it here and degrade gracefully:
    log a warning and return False so callers can fall back to a LIKE-based
    search instead of failing app startup.
    """
    try:
        already_existed = (
            session.execute(
                text(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='articles_fts'"
                )
            ).first()
            is not None
        )

        session.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
                    title, content, summary,
                    content='articles', content_rowid='id'
                )
                """
            )
        )

        session.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS articles_fts_ai AFTER INSERT ON articles BEGIN
                    INSERT INTO articles_fts(rowid, title, content, summary)
                    VALUES (new.id, new.title, new.content, new.summary);
                END
                """
            )
        )
        session.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS articles_fts_ad AFTER DELETE ON articles BEGIN
                    INSERT INTO articles_fts(articles_fts, rowid, title, content, summary)
                    VALUES ('delete', old.id, old.title, old.content, old.summary);
                END
                """
            )
        )
        session.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS articles_fts_au AFTER UPDATE ON articles BEGIN
                    INSERT INTO articles_fts(articles_fts, rowid, title, content, summary)
                    VALUES ('delete', old.id, old.title, old.content, old.summary);
                    INSERT INTO articles_fts(rowid, title, content, summary)
                    VALUES (new.id, new.title, new.content, new.summary);
                END
                """
            )
        )

        if not already_existed:
            # One-time backfill: index rows that existed before articles_fts did.
            session.execute(text("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')"))

        session.commit()
        return True
    except Exception as e:  # noqa: BLE001 — FTS5 may simply not be compiled in.
        session.rollback()
        logger.warning(
            "FTS5 full-text search unavailable (%s); search_articles() will use the LIKE fallback.",
            e,
        )
        return False


def init_db() -> None:
    """Create tables (if missing) and seed default categories + Manual Links feed."""
    # On first run of a packaged app, copy the bundled seed database.
    _copy_seed_db_if_first_run()

    Base.metadata.create_all(bind=engine)

    # create_all doesn't alter existing tables, so explicitly create any indexes
    # on existing tables that weren't already there (e.g., the compound index on
    # articles added post-migration).
    with SessionLocal() as session:
        session.execute(
            text("CREATE INDEX IF NOT EXISTS idx_articles_is_read_published ON articles(is_read, published_at DESC)")
        )

    with SessionLocal() as session:
        init_fts5_search(session)

    with SessionLocal() as session:
        for name, slug, sort_order in DEFAULT_CATEGORIES:
            stmt = (
                sqlite_insert(Category)
                .values(name=name, slug=slug, sort_order=sort_order)
                .on_conflict_do_nothing()
            )
            session.execute(stmt)

        session.commit()

        others_id = session.execute(
            select(Category.id).where(Category.slug == "others")
        ).scalar_one_or_none()

        if others_id is not None:
            stmt = (
                sqlite_insert(Feed)
                .values(category_id=others_id, **MANUAL_LINKS_FEED)
                .on_conflict_do_nothing()
            )
            session.execute(stmt)

        security_id = session.execute(
            select(Category.id).where(Category.slug == "security")
        ).scalar_one_or_none()

        if security_id is not None:
            security_feeds = [
                {"name": "Data Breaches", "url": "https://databreaches.net/feed/"},
                {"name": "Krebs on Security", "url": "https://krebsonsecurity.com/feed/"},
                {"name": "BleepingComputer", "url": "https://www.bleepingcomputer.com/feed/"},
                {"name": "The Hacker News", "url": "https://feeds.feedburner.com/TheHackersNews"},
                {"name": "Schneier on Security", "url": "https://www.schneier.com/feed/atom/"},
                {"name": "Hacker News", "url": "https://hnrss.org/frontpage"},
            ]
            for feed in security_feeds:
                stmt = (
                    sqlite_insert(Feed)
                    .values(category_id=security_id, **feed)
                    .on_conflict_do_nothing()
                )
                session.execute(stmt)

        sports_id = session.execute(
            select(Category.id).where(Category.slug == "sports")
        ).scalar_one_or_none()

        if sports_id is not None:
            sports_feeds = [
                {"name": "ESPN Tennis", "url": "https://www.espn.com/espn/rss/tennis/news"},
                {"name": "Sportsnet", "url": "https://www.sportsnet.ca/rss"},
                {"name": "ESPN Soccer", "url": "https://www.espn.com/espn/rss/soccer/news"},
            ]
            for feed in sports_feeds:
                stmt = (
                    sqlite_insert(Feed)
                    .values(category_id=sports_id, **feed)
                    .on_conflict_do_nothing()
                )
                session.execute(stmt)

        session.commit()

    logger.info("Database initialized (schema ensured, defaults seeded).")
