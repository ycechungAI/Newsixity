"""Tests for the weather-history repository layer (models + repository/weather.py).

Repository functions open their own ``with SessionLocal() as db:`` (no
dependency injection), so these tests point ``app.db.repository.weather``'s
module-level ``SessionLocal`` at an isolated in-memory SQLite engine instead
of the real on-disk database.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.db.repository import weather as weather_repo


def _iso(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


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


class TestWeatherLocations:
    def test_add_and_list_location(self, db_session_factory):
        loc_id = weather_repo.add_weather_location("London", "GB", 51.5074, -0.1278, sort_order=1)
        assert loc_id is not None

        locations = weather_repo.list_weather_locations()
        assert len(locations) == 1
        assert locations[0].id == loc_id
        assert locations[0].name == "London"
        assert locations[0].country == "GB"
        assert locations[0].latitude == 51.5074
        assert locations[0].longitude == -0.1278
        assert locations[0].sort_order == 1

    def test_duplicate_location_is_idempotent(self, db_session_factory):
        first_id = weather_repo.add_weather_location("Seoul", "KR", 37.5665, 126.9780)
        second_id = weather_repo.add_weather_location("Seoul", "KR", 37.5665, 126.9780)

        assert first_id == second_id
        locations = weather_repo.list_weather_locations()
        assert len(locations) == 1

    def test_different_coordinates_are_distinct_locations(self, db_session_factory):
        weather_repo.add_weather_location("Seoul", "KR", 37.5665, 126.9780)
        weather_repo.add_weather_location("London", "GB", 51.5074, -0.1278)

        locations = weather_repo.list_weather_locations()
        assert len(locations) == 2

    def test_delete_location_removes_history(self, db_session_factory):
        loc_id = weather_repo.add_weather_location("Seoul", "KR", 37.5665, 126.9780)
        weather_repo.add_weather_observation(loc_id, 20.0, 19.5, 55.0, 3.2, 1)
        weather_repo.upsert_weather_daily(
            loc_id, [{"date": "2026-07-20", "temp_max": 28.0, "temp_min": 19.0}]
        )

        weather_repo.delete_weather_location(loc_id)

        assert weather_repo.list_weather_locations() == []
        now = _iso(datetime.now(timezone.utc))
        assert weather_repo.get_weather_observations(loc_id, "1970-01-01T00:00:00.000Z", now) == []
        assert weather_repo.get_weather_daily(loc_id, "1970-01-01", "2099-01-01") == []


class TestWeatherObservations:
    def test_insert_and_read_observations_in_range(self, db_session_factory):
        loc_id = weather_repo.add_weather_location("Seoul", "KR", 37.5665, 126.9780)

        now = datetime.now(timezone.utc)
        in_range_1 = _iso(now - timedelta(hours=2))
        in_range_2 = _iso(now - timedelta(hours=1))
        out_of_range = _iso(now - timedelta(days=10))

        weather_repo.add_weather_observation(
            loc_id, 21.0, 20.5, 60.0, 2.1, 2, observed_at=in_range_1
        )
        weather_repo.add_weather_observation(
            loc_id, 22.0, 21.5, 58.0, 2.5, 3, observed_at=in_range_2
        )
        weather_repo.add_weather_observation(
            loc_id, 10.0, 9.0, 70.0, 1.0, 0, observed_at=out_of_range
        )

        range_start = _iso(now - timedelta(hours=3))
        range_end = _iso(now)
        rows = weather_repo.get_weather_observations(loc_id, range_start, range_end)

        assert [r.observed_at for r in rows] == [in_range_1, in_range_2]
        assert rows[0].temperature == 21.0
        assert rows[1].weather_code == 3

    def test_observations_scoped_to_location(self, db_session_factory):
        loc_a = weather_repo.add_weather_location("Seoul", "KR", 37.5665, 126.9780)
        loc_b = weather_repo.add_weather_location("London", "GB", 51.5074, -0.1278)

        now_iso = _iso(datetime.now(timezone.utc))
        weather_repo.add_weather_observation(loc_a, 20.0, 19.0, 50.0, 1.0, 1, observed_at=now_iso)
        weather_repo.add_weather_observation(loc_b, 15.0, 14.0, 80.0, 4.0, 3, observed_at=now_iso)

        rows = weather_repo.get_weather_observations(
            loc_a, "1970-01-01T00:00:00.000Z", "2099-01-01T00:00:00.000Z"
        )
        assert len(rows) == 1
        assert rows[0].location_id == loc_a

    def test_retention_deletes_only_old_observations(self, db_session_factory):
        loc_id = weather_repo.add_weather_location("Seoul", "KR", 37.5665, 126.9780)
        now = datetime.now(timezone.utc)

        old_ts = _iso(now - timedelta(days=45))
        recent_ts = _iso(now - timedelta(days=1))
        weather_repo.add_weather_observation(loc_id, 10.0, 9.0, 40.0, 1.0, 0, observed_at=old_ts)
        weather_repo.add_weather_observation(loc_id, 20.0, 19.0, 50.0, 2.0, 1, observed_at=recent_ts)

        deleted = weather_repo.delete_old_weather_observations(keep_days=30)

        assert deleted == 1
        remaining = weather_repo.get_weather_observations(
            loc_id, "1970-01-01T00:00:00.000Z", "2099-01-01T00:00:00.000Z"
        )
        assert len(remaining) == 1
        assert remaining[0].observed_at == recent_ts

    def test_retention_deletes_rows_landing_on_the_cutoff_day(self, db_session_factory):
        """A row a few hours past the cutoff must still be deleted.

        Regression guard: the cutoff was originally built with datetime(),
        which yields "2026-06-27 06:23:05" while observed_at holds
        "2026-06-27T06:23:05.530Z". String-comparing those puts 'T' (0x54)
        above the space (0x20), so nothing from the cutoff day was ever
        deleted. Only a same-day timestamp exposes that; a comfortably-old
        one passes either way.
        """
        loc_id = weather_repo.add_weather_location("Seoul", "KR", 37.5665, 126.9780)
        now = datetime.now(timezone.utc)

        # Same calendar day as the cutoff, but on the wrong side of it.
        just_past_cutoff = _iso(now - timedelta(days=30, hours=6))
        just_inside = _iso(now - timedelta(days=29, hours=18))
        weather_repo.add_weather_observation(
            loc_id, 10.0, 9.0, 40.0, 1.0, 0, observed_at=just_past_cutoff
        )
        weather_repo.add_weather_observation(
            loc_id, 20.0, 19.0, 50.0, 2.0, 1, observed_at=just_inside
        )

        deleted = weather_repo.delete_old_weather_observations(keep_days=30)

        assert deleted == 1
        remaining = weather_repo.get_weather_observations(
            loc_id, "1970-01-01T00:00:00.000Z", "2099-01-01T00:00:00.000Z"
        )
        assert [r.observed_at for r in remaining] == [just_inside]


class TestWeatherDaily:
    def test_upsert_creates_rows(self, db_session_factory):
        loc_id = weather_repo.add_weather_location("Seoul", "KR", 37.5665, 126.9780)

        count = weather_repo.upsert_weather_daily(
            loc_id,
            [
                {"date": "2026-07-20", "temp_max": 30.0, "temp_min": 22.0, "weather_code": 1},
                {"date": "2026-07-21", "temp_max": 31.0, "temp_min": 23.0, "weather_code": 2},
            ],
        )
        assert count == 2

        rows = weather_repo.get_weather_daily(loc_id, "2026-07-01", "2026-07-31")
        assert len(rows) == 2
        assert rows[0].date == "2026-07-20"
        assert rows[0].temp_max == 30.0

    def test_upsert_replaces_same_day_row_instead_of_duplicating(self, db_session_factory):
        loc_id = weather_repo.add_weather_location("Seoul", "KR", 37.5665, 126.9780)

        weather_repo.upsert_weather_daily(
            loc_id, [{"date": "2026-07-20", "temp_max": 30.0, "temp_min": 22.0}]
        )
        # Re-fetch the same day with revised numbers.
        weather_repo.upsert_weather_daily(
            loc_id, [{"date": "2026-07-20", "temp_max": 33.5, "temp_min": 24.0}]
        )

        rows = weather_repo.get_weather_daily(loc_id, "2026-07-01", "2026-07-31")
        assert len(rows) == 1
        assert rows[0].temp_max == 33.5
        assert rows[0].temp_min == 24.0

    def test_retention_deletes_only_old_daily_rows(self, db_session_factory):
        loc_id = weather_repo.add_weather_location("Seoul", "KR", 37.5665, 126.9780)
        today = datetime.now(timezone.utc).date()
        old_date = (today - timedelta(days=400)).isoformat()
        recent_date = (today - timedelta(days=1)).isoformat()

        weather_repo.upsert_weather_daily(
            loc_id,
            [
                {"date": old_date, "temp_max": 5.0, "temp_min": -2.0},
                {"date": recent_date, "temp_max": 28.0, "temp_min": 18.0},
            ],
        )

        deleted = weather_repo.delete_old_weather_daily(keep_days=365)

        assert deleted == 1
        remaining = weather_repo.get_weather_daily(loc_id, "1970-01-01", "2099-01-01")
        assert len(remaining) == 1
        assert remaining[0].date == recent_date
