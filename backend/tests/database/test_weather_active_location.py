"""Active-place selection for the weather page.

Before this, the selected place lived only in React state in WeatherTimeline,
so the page reset to the first saved city on every reload and the hero card
was pinned to a compile-time constant. These tests pin the persisted flag
that replaced it.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.db.repository import weather as weather_repo


@pytest.fixture
def db_session_factory(monkeypatch):
    """Isolated in-memory DB, wired into app.db.repository.weather.SessionLocal."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    monkeypatch.setattr(weather_repo, "SessionLocal", TestSessionLocal)
    return TestSessionLocal


class TestActiveLocation:
    def test_no_active_location_when_empty(self, db_session_factory):
        assert weather_repo.get_active_weather_location() is None

    def test_new_locations_default_to_inactive(self, db_session_factory):
        """Registering a city must not silently steal the selection."""
        loc_id = weather_repo.add_weather_location("London", "GB", 51.5074, -0.1278)
        locations = weather_repo.list_weather_locations()
        assert locations[0].is_active is False
        assert locations[0].id == loc_id

    def test_set_active_marks_exactly_one(self, db_session_factory):
        london = weather_repo.add_weather_location("London", "GB", 51.5074, -0.1278)
        seoul = weather_repo.add_weather_location("Seoul", "KR", 37.5665, 126.9780)

        weather_repo.set_active_weather_location(london)

        locations = weather_repo.list_weather_locations()
        assert [l.is_active for l in locations] == [True, False]
        assert weather_repo.get_active_weather_location().id == london

        # Switching must clear the previous one — two active rows would make
        # "which place is selected" ambiguous.
        weather_repo.set_active_weather_location(seoul)
        locations = weather_repo.list_weather_locations()
        assert [l.is_active for l in locations] == [False, True]
        assert weather_repo.get_active_weather_location().id == seoul

    def test_get_active_promotes_first_when_none_set(self, db_session_factory):
        """Existing installs have no active flag; pick one and persist it."""
        london = weather_repo.add_weather_location("London", "GB", 51.5074, -0.1278, sort_order=0)
        weather_repo.add_weather_location("Seoul", "KR", 37.5665, 126.9780, sort_order=1)

        active = weather_repo.get_active_weather_location()
        assert active.id == london

        # The promotion must stick, not just be recomputed each read.
        assert [l.is_active for l in weather_repo.list_weather_locations()] == [True, False]

    def test_deleting_active_location_falls_back(self, db_session_factory):
        """The DELETE route doesn't clear the flag, so reads must self-heal."""
        london = weather_repo.add_weather_location("London", "GB", 51.5074, -0.1278, sort_order=0)
        seoul = weather_repo.add_weather_location("Seoul", "KR", 37.5665, 126.9780, sort_order=1)
        weather_repo.set_active_weather_location(london)

        weather_repo.delete_weather_location(london)

        active = weather_repo.get_active_weather_location()
        assert active is not None
        assert active.id == seoul
        assert [l.is_active for l in weather_repo.list_weather_locations()] == [True]

    def test_set_active_for_unknown_id_leaves_nothing_flagged(self, db_session_factory):
        london = weather_repo.add_weather_location("London", "GB", 51.5074, -0.1278)
        weather_repo.set_active_weather_location(9999)

        assert [l.is_active for l in weather_repo.list_weather_locations()] == [False]
        # ...and the real one is still selectable.
        weather_repo.set_active_weather_location(london)
        assert weather_repo.get_active_weather_location().id == london