"""v0.5 category migration: Consumer Tech split and canonical ordering.

An upgraded install has two problems seeding alone cannot solve:

1. ``seed_feed()`` is keyed on URL alone and uses ON CONFLICT DO NOTHING, so a
   feed that already exists is never re-categorised. The four device-specific
   feeds stayed under technology and consumer-tech came up empty.
2. ``DEFAULT_CATEGORIES`` gained ``consumer-tech`` at sort_order 4, shifting
   every later category down. Existing rows keep their old numbers, so the new
   section sorted last instead of after Technology.

Both are handled by ``_migrate_categories_and_feeds``, which must be additive
and idempotent — it runs on every startup.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import importlib

# `import app.db.init_db as x` binds the *function* init_db (the module's most
# prominent name shadows the module in that form), so go through importlib to
# get the module object and monkeypatch its SessionLocal.
init_db_mod = importlib.import_module("app.db.init_db")

from app.db.init_db import (
    CATEGORY_ORDER_SLUGS,
    DEFAULT_CATEGORIES,
    FEED_CATEGORY_MOVES,
    _migrate_categories_and_feeds,
)
from app.db.models import Article, Base, Category, Feed

# The four feeds that must leave technology for consumer-tech.
MOVED_URLS = [url for url, _slug in FEED_CATEGORY_MOVES]
MOVE_SLUG = FEED_CATEGORY_MOVES[0][1]


@pytest.fixture
def session_factory(monkeypatch):
    """Isolated in-memory DB, wired into init_db's SessionLocal."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(init_db_mod, "SessionLocal", TestSessionLocal)
    return TestSessionLocal


def _seed_legacy(session_factory):
    """Build a pre-v0.5 database: technology holds all nine, no consumer-tech.

    Deliberately uses the *old* sort_order values, which is the whole point —
    the migration has to fix ordering on rows that already exist.
    """
    with session_factory() as db:
        tech = Category(name="Technology", slug="technology", sort_order=3)
        world = Category(name="World News", slug="world-news", sort_order=0)
        finance = Category(name="Finance", slug="finance", sort_order=1)
        db.add_all([tech, world, finance])
        db.flush()

        for url in MOVED_URLS:
            db.add(Feed(category_id=tech.id, name=f"moved {url}", url=url))
        db.add(Feed(category_id=tech.id, name="Ars Technica",
                    url="https://feeds.arstechnica.com/arstechnica/index"))
        db.add(Feed(category_id=world.id, name="Al Jazeera",
                    url="https://www.aljazeera.com/xml/rss/all.xml"))
        db.commit()
        return tech.id


def _add_missing_categories(session_factory):
    """What init_db does before the migration: ensure every slug exists.

    consumer-tech is new, so the migration must cope with a database that does
    not have it yet.
    """
    with session_factory() as db:
        for name, slug, _order in DEFAULT_CATEGORIES:
            exists = db.execute(
                select(Category.id).where(Category.slug == slug)
            ).scalar_one_or_none()
            if exists is None:
                db.add(Category(name=name, slug=slug, sort_order=99))
        db.commit()


class TestConsumerTechSplit:
    def test_device_feeds_move_out_of_technology(self, session_factory):
        tech_id = _seed_legacy(session_factory)
        _add_missing_categories(session_factory)

        with session_factory() as db:
            _migrate_categories_and_feeds(db)

        with session_factory() as db:
            by_url = {f.url: c.slug for f, c in db.execute(
                select(Feed, Category).join(Category, Feed.category_id == Category.id)
            )}
            assert all(by_url[u] == MOVE_SLUG for u in MOVED_URLS)
            # The industry feed must not be dragged along.
            assert by_url["https://feeds.arstechnica.com/arstechnica/index"] == "technology"
            assert tech_id is not None

    def test_other_categories_untouched(self, session_factory):
        _seed_legacy(session_factory)
        _add_missing_categories(session_factory)

        with session_factory() as db:
            _migrate_categories_and_feeds(db)

        with session_factory() as db:
            world = db.execute(
                select(Category).where(Category.slug == "world-news")
            ).scalar_one()
            assert world.name == "World News"

    def test_articles_survive_the_move(self, session_factory):
        """The move is an UPDATE on the feed row; its articles must still join."""
        _seed_legacy(session_factory)
        _add_missing_categories(session_factory)

        with session_factory() as db:
            feed = db.execute(
                select(Feed).where(Feed.url == MOVED_URLS[0])
            ).scalar_one()
            db.add(Article(
                feed_id=feed.id, guid="g1", title="kept", link="https://x/1",
                content=None, author=None, published_at=None,
                image_url=None,
            ))
            db.commit()

        with session_factory() as db:
            _migrate_categories_and_feeds(db)

        with session_factory() as db:
            article = db.scalars(select(Article)).one()
            feed = db.get(Feed, article.feed_id)
            category = db.get(Category, feed.category_id)
            assert article.title == "kept"
            assert category.slug == MOVE_SLUG


class TestCategoryOrdering:
    def test_sort_order_is_canonical(self, session_factory):
        _seed_legacy(session_factory)
        _add_missing_categories(session_factory)

        with session_factory() as db:
            _migrate_categories_and_feeds(db)

        with session_factory() as db:
            actual = [
                (c.slug, c.sort_order)
                for c in db.scalars(
                    select(Category).order_by(Category.sort_order)
                )
            ]
            expected = [
                (slug, i) for i, slug in enumerate(CATEGORY_ORDER_SLUGS)
                if any(s == slug for s, _ in actual)
            ]
            assert actual == expected

    def test_consumer_tech_sorts_after_technology(self, session_factory):
        _seed_legacy(session_factory)
        _add_missing_categories(session_factory)

        with session_factory() as db:
            _migrate_categories_and_feeds(db)

        with session_factory() as db:
            order = {c.slug: c.sort_order for c in db.scalars(select(Category))}
            assert order["consumer-tech"] == order["technology"] + 1


class TestIdempotence:
    def test_running_twice_changes_nothing(self, session_factory):
        """Runs on every startup, so a second pass must be a no-op."""
        _seed_legacy(session_factory)
        _add_missing_categories(session_factory)

        with session_factory() as db:
            _migrate_categories_and_feeds(db)
        with session_factory() as db:
            _migrate_categories_and_feeds(db)

        with session_factory() as db:
            feeds = list(db.scalars(select(Feed)))
            categories = list(db.scalars(select(Category)))
            # 4 moved + Ars + Al Jazeera; a second pass must add or drop none.
            assert len(feeds) == 6
            assert len(categories) == len(DEFAULT_CATEGORIES)

    def test_missing_category_is_skipped_not_fatal(self, session_factory):
        """consumer-tech may not exist yet; the move must be skipped, not crash."""
        _seed_legacy(session_factory)

        with session_factory() as db:
            _migrate_categories_and_feeds(db)  # no _add_missing_categories

        with session_factory() as db:
            by_url = {f.url: c.slug for f, c in db.execute(
                select(Feed, Category).join(Category, Feed.category_id == Category.id)
            )}
            assert by_url[MOVED_URLS[0]] == "technology"  # unchanged, not dropped