"""Daily briefing storage + generation (v0.4 §3), against a temp database."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

import app.db.repository.briefing as briefing_repo
import app.db.repository.feeds as feeds_module
from app.db.models import Article, Base, Category, Feed
from app.lib.integrations.ollama import OllamaUnavailableError
from app.lib.scheduler import briefing as service


@pytest.fixture
def db(tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path / 'b.db'}", connect_args={"check_same_thread": False})

    @event.listens_for(eng, "connect")
    def _fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    factory = sessionmaker(bind=eng, autoflush=False, future=True)
    monkeypatch.setattr(briefing_repo, "SessionLocal", factory)
    monkeypatch.setattr(feeds_module, "SessionLocal", factory)
    return factory


def _seed(db, *, slug, n, fetched_at="2026-10-02 12:00:00", feed_url=None, score=1.0):
    with db() as s:
        cat = s.query(Category).filter_by(slug=slug).one_or_none()
        if cat is None:
            cat = Category(name=slug, slug=slug)
            s.add(cat)
            s.flush()
        feed = Feed(name=f"{slug} feed {feed_url}", url=feed_url or f"https://{slug}.example/{n}", category_id=cat.id)
        s.add(feed)
        s.flush()
        for i in range(n):
            s.add(Article(feed_id=feed.id, guid=f"{slug}-{feed.id}-{i}", title=f"{slug} story {i}",
                          link=f"https://{slug}.example/a{i}", summary=f"Summary {i} of {slug}.",
                          fetched_at=fetched_at, relevance_score=score - i * 0.01))
        s.commit()


WINDOW = ("2026-10-02 00:00:00", "2026-10-03 00:00:00")


class TestCandidates:
    def test_per_category_cap_and_limit(self, db):
        _seed(db, slug="tech", n=10, score=9)
        _seed(db, slug="world", n=10, score=5)
        picked = briefing_repo.get_briefing_candidates(*WINDOW, limit=6, per_category=3)
        assert [c.category_slug for c in picked] == ["tech"] * 3 + ["world"] * 3

    def test_manual_links_and_weather_excluded(self, db):
        _seed(db, slug="others", n=3, feed_url="internal://manual", score=99)
        _seed(db, slug="weather", n=3, score=99)
        _seed(db, slug="tech", n=2)
        assert {c.category_slug for c in briefing_repo.get_briefing_candidates(*WINDOW)} == {"tech"}

    def test_window_bounds(self, db):
        _seed(db, slug="old", n=2, fetched_at="2026-10-01 23:59:59")
        _seed(db, slug="new", n=2, fetched_at="2026-10-03 00:00:00")
        _seed(db, slug="today", n=2, fetched_at="2026-10-02 00:00:00")
        assert {c.category_slug for c in briefing_repo.get_briefing_candidates(*WINDOW)} == {"today"}


class TestStorage:
    def test_save_overwrites_same_date(self, db):
        briefing_repo.save_briefing("2026-10-02", "first", [{"n": 1}], "m1")
        briefing_repo.save_briefing("2026-10-02", "second", [{"n": 2}], "m2")
        stored = briefing_repo.get_briefing("2026-10-02")
        assert (stored.content, stored.sources, stored.model) == ("second", [{"n": 2}], "m2")
        with db() as s:
            assert s.execute(text("SELECT count(*) FROM daily_briefing")).scalar() == 1
        assert briefing_repo.list_briefing_dates() == ["2026-10-02"]


class TestGeneration:
    @pytest.fixture
    def stubs(self, db, monkeypatch):
        calls = []

        async def model():
            return "test-model"

        async def write(articles, model=None):
            calls.append(articles)
            return "- **Tech:** things happened [1][2]."

        monkeypatch.setattr(service, "get_default_model", model)
        monkeypatch.setattr(service, "generate_briefing_text", write)
        monkeypatch.setattr(service, "_utc_window", lambda d: WINDOW)
        monkeypatch.setattr(service, "_generating", None)
        monkeypatch.setattr(service, "_last_error", {})
        return calls

    def run(self, coro):
        return asyncio.run(coro)

    def test_generates_and_stores_with_sources(self, db, stubs):
        _seed(db, slug="tech", n=4)
        assert self.run(service.generate_daily_briefing("2026-10-02")) == "generated"
        stored = briefing_repo.get_briefing("2026-10-02")
        assert stored.model == "test-model"
        assert stored.sources[0]["n"] == 1 and stored.sources[0]["articleId"]
        assert len(stubs[0]) == 3  # per-category cap

    def test_existing_briefing_is_served_not_regenerated(self, db, stubs):
        _seed(db, slug="tech", n=4)
        briefing_repo.save_briefing("2026-10-02", "cached", [], "m")
        assert self.run(service.generate_daily_briefing("2026-10-02")) == "exists"
        assert stubs == []
        assert briefing_repo.get_briefing("2026-10-02").content == "cached"

    def test_force_regenerates(self, db, stubs):
        _seed(db, slug="tech", n=4)
        briefing_repo.save_briefing("2026-10-02", "cached", [], "m")
        assert self.run(service.generate_daily_briefing("2026-10-02", force=True)) == "generated"
        assert briefing_repo.get_briefing("2026-10-02").content.startswith("- **Tech")

    def test_ollama_down_fails_cleanly(self, db, stubs, monkeypatch):
        _seed(db, slug="tech", n=4)

        async def down(*a, **k):
            raise OllamaUnavailableError("down")

        monkeypatch.setattr(service, "generate_briefing_text", down)
        assert self.run(service.generate_daily_briefing("2026-10-02")) == "failed"
        assert "Ollama" in service.last_error("2026-10-02")
        assert briefing_repo.get_briefing("2026-10-02") is None
        assert service.generating_date() is None  # claim released

    def test_too_few_articles(self, db, stubs):
        _seed(db, slug="tech", n=1)
        assert self.run(service.generate_daily_briefing("2026-10-02")) == "failed"
        assert "Not enough articles" in service.last_error("2026-10-02")

    def test_busy_while_claimed(self, db, stubs):
        assert service.try_claim("2026-10-01")
        assert self.run(service.generate_daily_briefing("2026-10-02")) == "busy"
        assert not service.try_claim("2026-10-02")
