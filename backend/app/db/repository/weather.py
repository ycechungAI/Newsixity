"""Weather queries — persisted cities, current-conditions observations, and

daily history. Precedent: ``MarketHeatmapSnapshot`` / ``repository/finance.py``
(unique-key upsert, ``DESC`` index, age-based retention). Reuses
``_js_iso_string`` from finance.py so timestamps stay byte-identical across
domains rather than each repository module growing its own formatter.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db.models import WeatherDaily as DailyModel
from app.db.models import WeatherLocation as LocationModel
from app.db.models import WeatherObservation as ObservationModel
from app.db.repository.finance import _js_iso_string
from app.db.session import SessionLocal


@dataclass
class WeatherLocationItem:
    id: int
    name: str
    country: str | None
    latitude: float
    longitude: float
    sort_order: int
    is_active: bool
    created_at: str


@dataclass
class WeatherObservationItem:
    id: int
    location_id: int
    observed_at: str
    temperature: float | None
    apparent_temperature: float | None
    humidity: float | None
    wind_speed: float | None
    weather_code: int | None


@dataclass
class WeatherDailyItem:
    id: int
    location_id: int
    date: str
    temp_max: float | None
    temp_min: float | None
    precipitation_sum: float | None
    weather_code: int | None
    wind_speed_max: float | None


def _row_to_location(row: LocationModel) -> WeatherLocationItem:
    return WeatherLocationItem(
        id=row.id,
        name=row.name,
        country=row.country,
        latitude=row.latitude,
        longitude=row.longitude,
        sort_order=row.sort_order,
        is_active=bool(row.is_active),
        created_at=row.created_at,
    )


def _row_to_observation(row: ObservationModel) -> WeatherObservationItem:
    return WeatherObservationItem(
        id=row.id,
        location_id=row.location_id,
        observed_at=row.observed_at,
        temperature=row.temperature,
        apparent_temperature=row.apparent_temperature,
        humidity=row.humidity,
        wind_speed=row.wind_speed,
        weather_code=row.weather_code,
    )


def _row_to_daily(row: DailyModel) -> WeatherDailyItem:
    return WeatherDailyItem(
        id=row.id,
        location_id=row.location_id,
        date=row.date,
        temp_max=row.temp_max,
        temp_min=row.temp_min,
        precipitation_sum=row.precipitation_sum,
        weather_code=row.weather_code,
        wind_speed_max=row.wind_speed_max,
    )


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

def list_weather_locations() -> list[WeatherLocationItem]:
    with SessionLocal() as db:
        rows = db.execute(
            select(LocationModel).order_by(LocationModel.sort_order, LocationModel.id)
        ).scalars().all()
        return [_row_to_location(r) for r in rows]


def add_weather_location(
    name: str,
    country: str | None,
    latitude: float,
    longitude: float,
    sort_order: int = 0,
) -> int:
    """Insert a city, keyed by (latitude, longitude).

    Idempotent: re-adding the same coordinates is a no-op (ON CONFLICT DO
    NOTHING) and returns the existing row's id rather than raising, so
    callers don't need to special-case "already added".
    """
    with SessionLocal() as db:
        stmt = sqlite_insert(LocationModel).values(
            name=name,
            country=country,
            latitude=latitude,
            longitude=longitude,
            sort_order=sort_order,
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["latitude", "longitude"])
        db.execute(stmt)
        db.commit()

        row_id = db.execute(
            select(LocationModel.id).where(
                LocationModel.latitude == latitude,
                LocationModel.longitude == longitude,
            )
        ).scalar_one()
        return row_id


def set_active_weather_location(location_id: int) -> None:
    """Make ``location_id`` the active place, clearing the flag elsewhere.

    Exactly one row may be active, so this runs in a single transaction:
    clear-all then set-one. Rows are only ever written one at a time here, so
    there is no window in which two are flagged.
    """
    with SessionLocal() as db:
        db.execute(update(LocationModel).values(is_active=0))
        db.execute(
            update(LocationModel)
            .where(LocationModel.id == location_id)
            .values(is_active=1)
        )
        db.commit()


def get_active_weather_location() -> WeatherLocationItem | None:
    """The persisted selection, or None if the user has never chosen one.

    Also self-heals: if the active row was deleted (the DELETE endpoint does
    not clear the flag), fall back to the first location so the page always
    has something to show, and persist that choice.
    """
    with SessionLocal() as db:
        row = db.execute(
            select(LocationModel)
            .where(LocationModel.is_active == 1)
            .order_by(LocationModel.sort_order, LocationModel.id)
            .limit(1)
        ).scalar_one_or_none()

        if row is None:
            row = db.execute(
                select(LocationModel)
                .order_by(LocationModel.sort_order, LocationModel.id)
                .limit(1)
            ).scalar_one_or_none()
            if row is not None:
                db.execute(
                    update(LocationModel).values(is_active=0)
                )
                db.execute(
                    update(LocationModel)
                    .where(LocationModel.id == row.id)
                    .values(is_active=1)
                )
                db.commit()

        return _row_to_location(row) if row is not None else None


def delete_weather_location(location_id: int) -> None:
    """Delete a location and its history in one round trip per table."""
    with SessionLocal() as db:
        db.execute(delete(ObservationModel).where(ObservationModel.location_id == location_id))
        db.execute(delete(DailyModel).where(DailyModel.location_id == location_id))
        db.execute(delete(LocationModel).where(LocationModel.id == location_id))
        db.commit()


# ---------------------------------------------------------------------------
# Observations (point-in-time current conditions)
# ---------------------------------------------------------------------------

def add_weather_observation(
    location_id: int,
    temperature: float | None,
    apparent_temperature: float | None,
    humidity: float | None,
    wind_speed: float | None,
    weather_code: int | None,
    observed_at: str | None = None,
) -> int:
    with SessionLocal() as db:
        obs = ObservationModel(
            location_id=location_id,
            observed_at=observed_at or _js_iso_string(datetime.now(timezone.utc)),
            temperature=temperature,
            apparent_temperature=apparent_temperature,
            humidity=humidity,
            wind_speed=wind_speed,
            weather_code=weather_code,
        )
        db.add(obs)
        db.commit()
        db.refresh(obs)
        return obs.id


def get_weather_observations(
    location_id: int, start: str, end: str
) -> list[WeatherObservationItem]:
    """Observations for a location with ``observed_at`` in [start, end], ascending."""
    with SessionLocal() as db:
        rows = db.execute(
            select(ObservationModel)
            .where(
                ObservationModel.location_id == location_id,
                ObservationModel.observed_at >= start,
                ObservationModel.observed_at <= end,
            )
            .order_by(ObservationModel.observed_at)
        ).scalars().all()
        return [_row_to_observation(r) for r in rows]


def delete_old_weather_observations(keep_days: int = 30) -> int:
    """Delete observations older than ``keep_days``. Single statement, not a per-row loop.

    The cutoff is built with strftime, not datetime(): observed_at holds the
    JS-ISO form ("...T06:23:05.530Z") while datetime() returns "... 06:23:05".
    Comparing those is a plain string compare, and 'T' (0x54) sorts above the
    space (0x20) — so every row from the cutoff day itself would survive no
    matter how old it was. strftime reproduces the stored format exactly.
    """
    cutoff = func.strftime("%Y-%m-%dT%H:%M:%fZ", "now", f"-{keep_days} days")
    with SessionLocal() as db:
        result = db.execute(
            delete(ObservationModel).where(ObservationModel.observed_at < cutoff)
        )
        db.commit()
        return result.rowcount


# ---------------------------------------------------------------------------
# Daily history
# ---------------------------------------------------------------------------

def upsert_weather_daily(location_id: int, rows: list[dict]) -> int:
    """Batch-upsert daily rows for a location in a single INSERT statement.

    Each ``rows`` item: ``{"date", "temp_max", "temp_min",
    "precipitation_sum", "weather_code", "wind_speed_max"}``. Re-fetching a
    day updates the existing (location_id, date) row rather than duplicating
    it — Open-Meteo's ``daily`` response is columnar parallel arrays, so
    callers pivot to this row shape before calling.
    """
    if not rows:
        return 0

    values = [
        {
            "location_id": location_id,
            "date": row["date"],
            "temp_max": row.get("temp_max"),
            "temp_min": row.get("temp_min"),
            "precipitation_sum": row.get("precipitation_sum"),
            "weather_code": row.get("weather_code"),
            "wind_speed_max": row.get("wind_speed_max"),
        }
        for row in rows
    ]

    with SessionLocal() as db:
        stmt = sqlite_insert(DailyModel).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["location_id", "date"],
            set_={
                "temp_max": stmt.excluded.temp_max,
                "temp_min": stmt.excluded.temp_min,
                "precipitation_sum": stmt.excluded.precipitation_sum,
                "weather_code": stmt.excluded.weather_code,
                "wind_speed_max": stmt.excluded.wind_speed_max,
            },
        )
        db.execute(stmt)
        db.commit()
        return len(values)


def get_weather_daily(
    location_id: int, start_date: str, end_date: str
) -> list[WeatherDailyItem]:
    """Daily rows for a location with ``date`` in [start_date, end_date], ascending."""
    with SessionLocal() as db:
        rows = db.execute(
            select(DailyModel)
            .where(
                DailyModel.location_id == location_id,
                DailyModel.date >= start_date,
                DailyModel.date <= end_date,
            )
            .order_by(DailyModel.date)
        ).scalars().all()
        return [_row_to_daily(r) for r in rows]


def delete_old_weather_daily(keep_days: int = 365) -> int:
    """Delete daily rows older than ``keep_days``. Single statement, not a per-row loop."""
    with SessionLocal() as db:
        result = db.execute(
            delete(DailyModel).where(
                DailyModel.date < func.date("now", f"-{keep_days} days")
            )
        )
        db.commit()
        return result.rowcount
