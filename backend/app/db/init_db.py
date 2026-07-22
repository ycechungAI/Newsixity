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

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

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


def init_db() -> None:
    """Create tables (if missing) and seed default categories + Manual Links feed."""
    # On first run of a packaged app, copy the bundled seed database.
    _copy_seed_db_if_first_run()

    Base.metadata.create_all(bind=engine)

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
            session.commit()

    logger.info("Database initialized (schema ensured, defaults seeded).")
