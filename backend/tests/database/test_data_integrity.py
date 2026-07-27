"""Data-integrity tests — the failures you cannot see from the UI.

These cover the ways the database can quietly go wrong while every screen
still looks fine:

  * the FTS5 index drifting out of sync with `articles` (search silently
    returns stale, missing, or deleted rows — no error anywhere),
  * upserts duplicating rows instead of updating them,
  * retention deleting the wrong side of a cutoff,
  * cascade deletes orphaning child rows,
  * a restore losing or corrupting data.

Each test asserts an invariant about *stored state*, not about a return
value, so a regression shows up here rather than as a confusing UI report.
"""

from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

import app.db.repository.articles as articles_module
import app.db.repository.weather as weather_module
from app.db.init_db import init_fts5_search
from app.db.models import Article, Base, Category, Feed


@pytest.fixture
def engine(tmp_path):
    """Real on-disk SQLite, so triggers and WAL behave as in production."""
    eng = create_engine(
        f"sqlite:///{tmp_path / 'integrity.db'}",
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(eng, "connect")
    def _fk_on(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session_factory(engine, monkeypatch):
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    monkeypatch.setattr(articles_module, "SessionLocal", factory)
    monkeypatch.setattr(weather_module, "SessionLocal", factory)
    with factory() as s:
        init_fts5_search(s)
        s.commit()
    return factory


def _feed(session_factory) -> int:
    with session_factory() as s:
        cat = Category(name="World", slug="world")
        s.add(cat)
        s.flush()
        feed = Feed(name="F", url="https://e.com/f.xml", category_id=cat.id)
        s.add(feed)
        s.flush()
        s.commit()
        return feed.id


def _add(session_factory, feed_id, *, guid, title, content="", summary=None) -> int:
    with session_factory() as s:
        a = Article(
            feed_id=feed_id, guid=guid, title=title, link=f"https://e.com/{guid}",
            content=content, summary=summary, published_at="2026-07-27T00:00:00.000Z",
        )
        s.add(a)
        s.flush()
        s.commit()
        return a.id


def _fts_count(session_factory, term: str) -> int:
    with session_factory() as s:
        return s.execute(
            text("SELECT count(*) FROM articles_fts WHERE articles_fts MATCH :q"),
            {"q": f'"{term}"'},
        ).scalar()


def _index_size(session_factory) -> int:
    with session_factory() as s:
        return s.execute(text("SELECT count(*) FROM articles_fts")).scalar()


def _article_count(session_factory) -> int:
    with session_factory() as s:
        return s.execute(text("SELECT count(*) FROM articles")).scalar()


class TestFts5StaysInSyncWithArticles:
    """The index is external-content: only triggers keep it truthful.

    If one misfires there is no error — searches just return the wrong
    thing, which is exactly the sort of rot that survives manual QA.
    """

    def test_insert_is_indexed(self, session_factory):
        fid = _feed(session_factory)
        _add(session_factory, fid, guid="g1", title="Quokka sightings", content="body")
        assert _fts_count(session_factory, "quokka") == 1

    def test_update_reindexes_and_drops_the_old_terms(self, session_factory):
        fid = _feed(session_factory)
        aid = _add(session_factory, fid, guid="g1", title="Quokka sightings", content="body")

        with session_factory() as s:
            s.execute(text("UPDATE articles SET title='Wombat sightings' WHERE id=:i"), {"i": aid})
            s.commit()

        assert _fts_count(session_factory, "wombat") == 1
        # The stale term must go, or search keeps returning renamed articles.
        assert _fts_count(session_factory, "quokka") == 0

    def test_delete_removes_from_the_index(self, session_factory):
        fid = _feed(session_factory)
        aid = _add(session_factory, fid, guid="g1", title="Quokka sightings", content="body")

        with session_factory() as s:
            s.execute(text("DELETE FROM articles WHERE id=:i"), {"i": aid})
            s.commit()

        assert _fts_count(session_factory, "quokka") == 0
        assert _index_size(session_factory) == _article_count(session_factory)

    def test_summary_write_is_indexed(self, session_factory):
        """Summaries are searchable, so the summarizer's write must reindex."""
        fid = _feed(session_factory)
        aid = _add(session_factory, fid, guid="g1", title="Plain", content="body")
        articles_module.update_article_summary(aid, "A pangolin explainer.", "test-model")
        assert _fts_count(session_factory, "pangolin") == 1

    def test_index_size_tracks_articles_through_churn(self, session_factory):
        """The invariant that catches drift: one index row per article."""
        fid = _feed(session_factory)
        ids = [
            _add(session_factory, fid, guid=f"g{i}", title=f"Title {i}", content="body")
            for i in range(12)
        ]
        with session_factory() as s:
            for aid in ids[:4]:
                s.execute(text("DELETE FROM articles WHERE id=:i"), {"i": aid})
            for aid in ids[4:8]:
                s.execute(text("UPDATE articles SET content='changed' WHERE id=:i"), {"i": aid})
            s.commit()

        assert _index_size(session_factory) == _article_count(session_factory) == 8

    def test_integrity_check_passes_after_churn(self, session_factory):
        """FTS5's own consistency check — catches a corrupt index directly."""
        fid = _feed(session_factory)
        aid = _add(session_factory, fid, guid="g1", title="Quokka", content="body")
        with session_factory() as s:
            s.execute(text("UPDATE articles SET title='Wombat' WHERE id=:i"), {"i": aid})
            s.execute(text("DELETE FROM articles WHERE id=:i"), {"i": aid})
            s.commit()
            # Raises if the index disagrees with the content table.
            s.execute(text("INSERT INTO articles_fts(articles_fts) VALUES('integrity-check')"))

    def test_rebuild_is_idempotent(self, session_factory):
        """init_fts5_search runs on every startup; it must not double-index."""
        fid = _feed(session_factory)
        _add(session_factory, fid, guid="g1", title="Quokka", content="body")
        before = _index_size(session_factory)

        with session_factory() as s:
            init_fts5_search(s)
            s.commit()

        assert _index_size(session_factory) == before
        assert _fts_count(session_factory, "quokka") == 1


class TestNoDuplicateRowsOnRepeatedWrites:
    def test_reupserting_a_day_updates_rather_than_duplicates(self, session_factory):
        """Re-fetching weather for a day must not grow the table."""
        loc = weather_module.add_weather_location("Oslo", "NO", 59.91, 10.75)
        rows = [{"date": "2026-07-01", "temp_max": 20.0, "temp_min": 10.0,
                 "precipitation_sum": 0.0, "weather_code": 1, "wind_speed_max": 5.0}]

        weather_module.upsert_weather_daily(loc, rows)
        rows[0]["temp_max"] = 25.0
        weather_module.upsert_weather_daily(loc, rows)

        stored = weather_module.get_weather_daily(loc, "2026-01-01", "2026-12-31")
        assert len(stored) == 1, "same (location, date) must update, not duplicate"
        assert stored[0].temp_max == 25.0, "the newer value must win"

    def test_readding_a_city_does_not_duplicate_it(self, session_factory):
        a = weather_module.add_weather_location("Oslo", "NO", 59.91, 10.75)
        b = weather_module.add_weather_location("Oslo", "NO", 59.91, 10.75)
        assert a == b
        assert len(weather_module.list_weather_locations()) == 1


class TestCascadeDeletesLeaveNoOrphans:
    def test_deleting_a_city_removes_its_history(self, session_factory):
        loc = weather_module.add_weather_location("Oslo", "NO", 59.91, 10.75)
        weather_module.add_weather_observation(loc, 20.0, 19.0, 50.0, 3.0, 1)
        weather_module.upsert_weather_daily(loc, [{
            "date": "2026-07-01", "temp_max": 20.0, "temp_min": 10.0,
            "precipitation_sum": 0.0, "weather_code": 1, "wind_speed_max": 5.0,
        }])

        weather_module.delete_weather_location(loc)

        assert weather_module.get_weather_daily(loc, "2000-01-01", "2100-01-01") == []
        assert weather_module.get_weather_observations(
            loc, "1970-01-01T00:00:00.000Z", "2099-01-01T00:00:00.000Z"
        ) == []

    def test_no_foreign_key_violations_remain(self, session_factory):
        """SQLite's own orphan check over the whole database."""
        loc = weather_module.add_weather_location("Oslo", "NO", 59.91, 10.75)
        weather_module.add_weather_observation(loc, 20.0, 19.0, 50.0, 3.0, 1)
        weather_module.delete_weather_location(loc)

        with session_factory() as s:
            assert s.execute(text("PRAGMA foreign_key_check")).fetchall() == []


class TestRetentionDeletesOnlyTheRightSide:
    def test_daily_retention_keeps_recent_and_drops_old(self, session_factory):
        from datetime import date, timedelta

        loc = weather_module.add_weather_location("Oslo", "NO", 59.91, 10.75)
        today = date.today()
        old = (today - timedelta(days=400)).isoformat()
        recent = (today - timedelta(days=5)).isoformat()
        weather_module.upsert_weather_daily(loc, [
            {"date": old, "temp_max": 1.0, "temp_min": 0.0, "precipitation_sum": 0.0,
             "weather_code": 1, "wind_speed_max": 1.0},
            {"date": recent, "temp_max": 2.0, "temp_min": 1.0, "precipitation_sum": 0.0,
             "weather_code": 1, "wind_speed_max": 1.0},
        ])

        deleted = weather_module.delete_old_weather_daily(keep_days=365)

        assert deleted == 1
        remaining = weather_module.get_weather_daily(loc, "1900-01-01", "2999-12-31")
        assert [r.date for r in remaining] == [recent]


class TestBackupRestorePreservesData:
    """A restore must reproduce the source exactly — this is the one that
    would otherwise be discovered as missing articles, long after the fact."""

    def test_vacuum_into_snapshot_preserves_every_row(self, session_factory, tmp_path):
        from app.lib.backup.restore import _snapshot_db, _validate_sqlite_file

        fid = _feed(session_factory)
        for i in range(25):
            _add(session_factory, fid, guid=f"g{i}", title=f"Title {i}", content="body")

        with session_factory() as s:
            src = s.get_bind().url.database
            expected = s.execute(text("SELECT count(*) FROM articles")).scalar()

        snapshot = tmp_path / "snap.db"
        _snapshot_db(__import__("pathlib").Path(src), snapshot)

        conn = sqlite3.connect(str(snapshot))
        try:
            assert conn.execute("SELECT count(*) FROM articles").fetchone()[0] == expected
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        finally:
            conn.close()

    def test_snapshot_passes_the_import_gate(self, session_factory, tmp_path):
        """A backup this app produces must be one this app will accept back."""
        from app.lib.backup.restore import _snapshot_db, _validate_sqlite_file

        _feed(session_factory)
        with session_factory() as s:
            src = s.get_bind().url.database
            # The gate requires the core tables; make sure they exist here.
            s.execute(text("CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, key TEXT)"))
            s.commit()

        snapshot = tmp_path / "snap2.db"
        _snapshot_db(__import__("pathlib").Path(src), snapshot)
        _validate_sqlite_file(snapshot)  # must not raise
