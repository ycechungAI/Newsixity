"""Hourly weather history (v0.4 §4).

Observations used to be recorded only as a side effect of someone viewing a
forecast, so a machine left idle recorded nothing. This job records current
conditions for every saved city once an hour, and applies the retention
windows that were defined but never called.
"""

from __future__ import annotations

import asyncio
import logging

from app.db.repository import (
    add_weather_observation,
    delete_old_weather_daily,
    delete_old_weather_observations,
    list_weather_locations,
    upsert_weather_daily,
)
from app.lib.integrations.weather import daily_rows_from_response, fetch_forecast

logger = logging.getLogger("newsixity")


def record_forecast(location_id: int, data: dict) -> None:
    """Persist a forecast response's current conditions + daily rows."""
    current = data.get("current") or {}
    add_weather_observation(
        location_id=location_id,
        temperature=current.get("temperature_2m"),
        apparent_temperature=current.get("apparent_temperature"),
        humidity=current.get("relative_humidity_2m"),
        wind_speed=current.get("wind_speed_10m"),
        weather_code=current.get("weather_code"),
    )
    rows = daily_rows_from_response(data)
    if rows:
        upsert_weather_daily(location_id, rows)


def _record_all_sync() -> tuple[int, int]:
    recorded = failed = 0
    for location in list_weather_locations():
        # Best-effort per city: one unreachable forecast must not stop the rest.
        try:
            record_forecast(location.id, fetch_forecast(location.latitude, location.longitude))
            recorded += 1
        except Exception as e:  # noqa: BLE001
            failed += 1
            logger.warning("[Newsixity] Hourly weather for %s failed: %s", location.name, e)
    delete_old_weather_observations()
    delete_old_weather_daily()
    return recorded, failed


async def record_weather_for_saved_locations() -> None:
    recorded, failed = await asyncio.to_thread(_record_all_sync)
    if recorded or failed:
        logger.info("[Newsixity] Hourly weather: %d recorded, %d failed", recorded, failed)
