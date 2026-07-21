"""Schema creation and default seeding — port of the tail of schema.ts.

``create_all`` only creates missing tables, so this is safe to run against the
existing production database. Seeding uses INSERT-OR-IGNORE semantics, matching
the Node ``INSERT OR IGNORE`` calls, so it is idempotent.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

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


def init_db() -> None:
    """Create tables (if missing) and seed default categories + Manual Links feed."""
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
