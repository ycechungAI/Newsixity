"""Weather endpoints — /api/weather/*.

Proxies Open-Meteo (so the browser no longer calls a third party directly)
and persists what it fetches, which is what makes history and timelines
possible. Saved cities live in the DB rather than component state, so they
survive a reload.

Note routes must NOT repeat the /api prefix — main.py adds it when including
the router.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.repository import (
    add_weather_location,
    add_weather_observation,
    delete_weather_location,
    get_weather_daily,
    get_weather_observations,
    list_weather_locations,
    upsert_weather_daily,
)
from app.lib.integrations.weather import (
    daily_rows_from_response,
    fetch_archive,
    fetch_forecast,
    search_cities,
)
from app.lib.server.rate_limit import TEN_MIN_MS, rate_limit

logger = logging.getLogger("newsixity")

router = APIRouter()

MAX_ARCHIVE_DAYS = 365 * 5


def _validate_coords(latitude: float, longitude: float) -> None:
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        raise HTTPException(status_code=400, detail="Invalid coordinates")


@router.get(
    "/weather/forecast",
    dependencies=[Depends(rate_limit("weather-forecast", 120, TEN_MIN_MS))],
)
async def get_forecast(
    latitude: float = Query(...),
    longitude: float = Query(...),
    days: int = Query(7, ge=1, le=16),
) -> dict:
    """Current conditions + forecast, recording an observation as a side effect.

    The observation write is best-effort: a failure to persist history must
    never cost the user their forecast, which is the thing they actually
    asked for.
    """
    _validate_coords(latitude, longitude)
    try:
        data = await asyncio.to_thread(fetch_forecast, latitude, longitude, days)
    except Exception as e:  # noqa: BLE001
        logger.error("[Newsixity] Weather forecast fetch failed: %s", e)
        raise HTTPException(status_code=502, detail="Weather service unavailable") from e

    try:
        await asyncio.to_thread(_record_observation, latitude, longitude, data)
    except Exception as e:  # noqa: BLE001
        logger.warning("[Newsixity] Could not record weather observation: %s", e)

    return data


def _record_observation(latitude: float, longitude: float, data: dict) -> None:
    """Persist current conditions + the forecast's daily rows, if this is a saved city."""
    location = _find_location(latitude, longitude)
    if not location:
        return  # Only track history for cities the user actually saved.

    current = data.get("current") or {}
    add_weather_observation(
        location_id=location.id,
        temperature=current.get("temperature_2m"),
        apparent_temperature=current.get("apparent_temperature"),
        humidity=current.get("relative_humidity_2m"),
        wind_speed=current.get("wind_speed_10m"),
        weather_code=current.get("weather_code"),
    )

    rows = daily_rows_from_response(data)
    if rows:
        upsert_weather_daily(location.id, rows)


def _find_location(latitude: float, longitude: float):
    """Match a saved city by coordinate, tolerating float formatting drift.

    The frontend round-trips coordinates through strings, so exact equality
    is unreliable; ~0.01 degrees is far tighter than the forecast grid.
    """
    for loc in list_weather_locations():
        if abs(loc.latitude - latitude) < 0.01 and abs(loc.longitude - longitude) < 0.01:
            return loc
    return None


@router.get(
    "/weather/search",
    dependencies=[Depends(rate_limit("weather-search", 60, TEN_MIN_MS))],
)
async def search(q: str = Query(..., min_length=1, max_length=100)) -> dict:
    try:
        return await asyncio.to_thread(search_cities, q)
    except Exception as e:  # noqa: BLE001
        logger.error("[Newsixity] City search failed: %s", e)
        raise HTTPException(status_code=502, detail="Geocoding service unavailable") from e


@router.get("/weather/locations")
async def get_locations() -> dict:
    locations = await asyncio.to_thread(list_weather_locations)
    return {
        "locations": [
            {
                "id": loc.id,
                "name": loc.name,
                "country": loc.country,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "sortOrder": loc.sort_order,
            }
            for loc in locations
        ]
    }


@router.post(
    "/weather/locations",
    dependencies=[Depends(rate_limit("weather-add-location", 60, TEN_MIN_MS))],
)
async def add_location(
    name: str = Query(..., min_length=1, max_length=120),
    latitude: float = Query(...),
    longitude: float = Query(...),
    country: str | None = Query(None, max_length=120),
) -> dict:
    _validate_coords(latitude, longitude)
    location_id = await asyncio.to_thread(
        add_weather_location, name, country, latitude, longitude, 0
    )
    return {"id": location_id, "name": name}


@router.delete("/weather/locations/{location_id}")
async def remove_location(location_id: int) -> dict:
    await asyncio.to_thread(delete_weather_location, location_id)
    return {"success": True}


@router.get(
    "/weather/history",
    dependencies=[Depends(rate_limit("weather-history", 120, TEN_MIN_MS))],
)
async def get_history(
    location_id: int = Query(...),
    days: int = Query(30, ge=1, le=MAX_ARCHIVE_DAYS),
) -> dict:
    """Stored daily history for a saved city, most recent last."""
    end = date.today()
    start = end - timedelta(days=days)
    rows = await asyncio.to_thread(
        get_weather_daily, location_id, start.isoformat(), end.isoformat()
    )
    return {
        "days": [
            {
                "date": r.date,
                "tempMax": r.temp_max,
                "tempMin": r.temp_min,
                "precipitation": r.precipitation_sum,
                "weatherCode": r.weather_code,
                "windSpeedMax": r.wind_speed_max,
            }
            for r in rows
        ]
    }


@router.get(
    "/weather/observations",
    dependencies=[Depends(rate_limit("weather-observations", 120, TEN_MIN_MS))],
)
async def get_observations(
    location_id: int = Query(...),
    hours: int = Query(48, ge=1, le=24 * 90),
) -> dict:
    """Point-in-time readings — a finer-grained view than the daily rows."""
    from datetime import datetime, timezone

    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)

    def _iso(dt) -> str:
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"

    rows = await asyncio.to_thread(
        get_weather_observations, location_id, _iso(start), _iso(end)
    )
    return {
        "observations": [
            {
                "observedAt": r.observed_at,
                "temperature": r.temperature,
                "apparentTemperature": r.apparent_temperature,
                "humidity": r.humidity,
                "windSpeed": r.wind_speed,
                "weatherCode": r.weather_code,
            }
            for r in rows
        ]
    }


@router.post(
    "/weather/backfill",
    dependencies=[Depends(rate_limit("weather-backfill", 10, TEN_MIN_MS))],
)
async def backfill(
    location_id: int = Query(...),
    days: int = Query(365, ge=1, le=MAX_ARCHIVE_DAYS),
) -> dict:
    """Populate history from Open-Meteo's archive.

    Without this the timeline is empty until the app has been running for
    weeks. The archive is free and goes back decades, so history is useful
    immediately.
    """
    locations = await asyncio.to_thread(list_weather_locations)
    location = next((loc for loc in locations if loc.id == location_id), None)
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    # The archive lags real time by a couple of days; asking for today
    # returns nulls rather than an error, so stop short of it.
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=days)

    try:
        data = await asyncio.to_thread(
            fetch_archive, location.latitude, location.longitude,
            start.isoformat(), end.isoformat(),
        )
    except Exception as e:  # noqa: BLE001
        logger.error("[Newsixity] Weather archive backfill failed: %s", e)
        raise HTTPException(status_code=502, detail="Archive service unavailable") from e

    rows = [r for r in daily_rows_from_response(data) if r.get("temp_max") is not None]
    written = await asyncio.to_thread(upsert_weather_daily, location_id, rows)
    return {"success": True, "days": written}
