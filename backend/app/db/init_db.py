"""Schema creation and default seeding — port of the tail of schema.ts.

``create_all`` only creates missing tables, so this is safe to run against the
existing production database. Seeding uses INSERT-OR-IGNORE semantics, matching
the Node ``INSERT OR IGNORE`` calls, so it is idempotent.
"""

from __future__ import annotations

import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.db.base import Base
from app.db.models import Category, Feed, PodcastEpisode
from app.db.repository.feeds import get_deleted_feed_urls
from app.db.session import engine, SessionLocal

logger = logging.getLogger(__name__)

# (name, slug, sort_order) — identical ordering to schema.ts.
DEFAULT_CATEGORIES: list[tuple[str, str, int]] = [
    ("World News", "world-news", 0),
    ("Finance", "finance", 1),
    ("Gaming", "gaming", 2),
    ("Technology", "technology", 3),
    ("Consumer Tech", "consumer-tech", 4),
    ("Sports", "sports", 5),
    ("Weather", "weather", 6),
    ("Top News", "top-news", 7),
    ("Others", "others", 8),
    ("Security", "security", 10),
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


def _add_column_if_missing(session: Session, table: str, column: str, ddl: str) -> None:
    """ALTER TABLE ... ADD COLUMN, but only if the column isn't already there.

    There is no migration framework in this project, so columns introduced
    after a table shipped are backfilled here at startup. Checking first keeps
    it idempotent — SQLite has no ``ADD COLUMN IF NOT EXISTS``, and a bare
    re-run would fail on the duplicate.
    """
    existing = {
        row[1] for row in session.execute(text(f"PRAGMA table_info({table})"))
    }
    if not existing:
        return  # table itself doesn't exist yet; create_all will make it whole
    if column in existing:
        return
    logger.info("[Newsixity] Adding %s.%s to existing database", table, column)
    session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


# Feeds that changed category in v0.5. seed_feed() is keyed on URL alone and
# uses ON CONFLICT DO NOTHING, so an existing feed is never re-categorised by
# seeding alone — without this an upgraded install keeps the four device feeds
# under technology forever and consumer-tech stays empty.
FEED_CATEGORY_MOVES: list[tuple[str, str]] = [
    ("https://9to5google.com/feed/", "consumer-tech"),
    ("https://9to5mac.com/feed/", "consumer-tech"),
    ("https://www.tomshardware.com/feeds/all", "consumer-tech"),
    (
        "https://www.newyorker.com/feed/science/science-and-technology/rss",
        "consumer-tech",
    ),
]

# DEFAULT_CATEGORIES sort_order changed in v0.5 (consumer-tech inserted at 4,
# everything after shifted down). Existing rows keep their old numbers, which
# would place the new section last. Re-apply the canonical ordering.
CATEGORY_ORDER_SLUGS = [slug for _name, slug, _order in DEFAULT_CATEGORIES]


def _migrate_categories_and_feeds(session: Session) -> None:
    """Re-apply canonical category ordering and v0.5 feed moves.

    Additive and idempotent: only writes rows whose current value differs, and
    never inserts or deletes a feed or a category. Safe to run on every
    startup.
    """
    # Canonical sort_order. The unique slug is the natural key, so this works
    # regardless of the ids the categories happen to have.
    for desired_order, slug in enumerate(CATEGORY_ORDER_SLUGS):
        session.execute(
            update(Category)
            .where(Category.slug == slug)
            .values(sort_order=desired_order)
        )

    for url, slug in FEED_CATEGORY_MOVES:
        target = session.execute(
            select(Category.id).where(Category.slug == slug)
        ).scalar_one_or_none()
        if target is None:
            # consumer-tech doesn't exist yet — init_db seeds it just above.
            continue
        session.execute(
            update(Feed).where(Feed.url == url).values(category_id=target)
        )

    session.commit()


def _normalize_podcast_episode_dates(session: Session) -> None:
    """Backfill: normalize podcast episode ``published_at`` to ISO-8601.

    Older builds stored the raw RFC822 ``published`` string (e.g.
    ``"Wed, 9 Sep 2020 09:56:18 +0000"``). Lexicographic ``ORDER BY`` on those
    sorts by day-of-month and scrambles episode ordering. Normalize any rows
    that don't already look like ISO-8601 into UTC ISO format. Idempotent and
    fast to run on every startup (only touches non-ISO rows).
    """
    from email.utils import parsedate_to_datetime

    rows = session.execute(
        text(
            "SELECT id, published_at FROM podcast_episodes "
            "WHERE published_at IS NOT NULL AND published_at != ''"
        )
    ).fetchall()

    normalized = 0
    for row in rows:
        raw: str = row.published_at
        # Skip values already normalized on a previous run.
        try:
            datetime.fromisoformat(raw.replace("Z", "+00:00"))
            continue
        except (ValueError, TypeError):
            pass

        try:
            parsed = parsedate_to_datetime(raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            session.execute(
                text("UPDATE podcast_episodes SET published_at = :iso WHERE id = :id"),
                {"iso": parsed.isoformat(), "id": row.id},
            )
            normalized += 1
        except (ValueError, TypeError):
            continue

    if normalized:
        session.commit()
        logger.info(
            "[Newsixity] Normalized %d podcast episode dates to ISO-8601", normalized
        )


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

        # Columns added after the tables were first created. create_all never
        # alters an existing table, so an upgraded install would fail every
        # SELECT that names them with "no such column".
        _add_column_if_missing(session, "weather_locations", "is_active",
                               "INTEGER NOT NULL DEFAULT 0")
        session.commit()

    with SessionLocal() as session:
        init_fts5_search(session)

    with SessionLocal() as session:
        _normalize_podcast_episode_dates(session)

    with SessionLocal() as session:
        # Default feeds the user deleted stay deleted (v0.4 §1).
        deleted_urls = get_deleted_feed_urls(session)

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

        # Every other default feed — including security and sports — lives in
        # DEFAULT_FEEDS (app/lib/rss/feeds.py), so there is a single list of
        # what a fresh install gets. Those two used to be duplicated here, which
        # is how Hacker News ended up seeded under two different categories at
        # once: seed_all_feeds() runs on every refresh and keys on URL alone.

        session.commit()

    with SessionLocal() as session:
        _migrate_categories_and_feeds(session)

    logger.info("Database initialized (schema ensured, defaults seeded).")
