"""Open-Meteo client — forecast, geocoding, and historical archive.

Why this exists server-side at all: the frontend used to call Open-Meteo
straight from the browser. That works for Open-Meteo specifically (it sends
permissive CORS headers), but it means every mount refires the requests, the
results can never be persisted, and the app depends on a third-party CORS
policy it does not control — the same assumption that silently broke the
YouTube playlist feature. Routing through the backend fixes all three and is
what makes weather history possible.

Open-Meteo needs no API key. All outbound fetches go through the shared SSRF
gate, matching lib/utils/video.py and lib/podcast/parser.py.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx

from app.lib.integrations.content import resolves_to_blocked_ip
from app.lib.utils.url import parse_http_url

logger = logging.getLogger("newsixity")

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

TIMEOUT_SECONDS = 15

# Forecast changes on the order of tens of minutes; 10 is a good balance
# between freshness and not hammering a free service on every tab switch.
FORECAST_CACHE_SECONDS = 10 * 60
# Place coordinates essentially never change.
GEOCODING_CACHE_SECONDS = 24 * 60 * 60
# Historical data for a closed date is immutable.
ARCHIVE_CACHE_SECONDS = 24 * 60 * 60

_cache: dict[str, tuple[float, Any]] = {}

DAILY_FIELDS = (
    "temperature_2m_max,temperature_2m_min,weather_code,"
    "precipitation_sum,wind_speed_10m_max"
)
CURRENT_FIELDS = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,"
    "weather_code,wind_speed_10m"
)


def _cached(key: str, ttl: int):
    entry = _cache.get(key)
    if entry and (time.time() - entry[0]) < ttl:
        return entry[1]
    return None


def _store(key: str, value: Any) -> None:
    _cache[key] = (time.time(), value)


def _guarded_get(url: str) -> Any:
    """Fetch through the shared SSRF gate and return parsed JSON.

    The host is hardcoded above and only query parameters vary, so this is
    defence in depth rather than the primary control — but it keeps every
    outbound fetch in the codebase going through one door.
    """
    safe_url = parse_http_url(url)
    if not safe_url:
        raise ValueError("Not a valid http/https URL")
    if resolves_to_blocked_ip(urlparse(safe_url).hostname):
        raise ValueError("URL resolves to a blocked address")

    response = httpx.get(safe_url, timeout=TIMEOUT_SECONDS, follow_redirects=True)
    response.raise_for_status()
    return response.json()


def fetch_forecast(latitude: float, longitude: float, days: int = 7) -> dict:
    """Current conditions + daily forecast for a coordinate."""
    # Round the cache key: the UI sends coordinates with more precision than
    # the forecast grid resolves, so unrounded keys would miss constantly.
    key = f"forecast:{latitude:.3f},{longitude:.3f},{days}"
    hit = _cached(key, FORECAST_CACHE_SECONDS)
    if hit is not None:
        return hit

    params = urlencode({
        "latitude": latitude,
        "longitude": longitude,
        "daily": DAILY_FIELDS,
        "current": CURRENT_FIELDS,
        "timezone": "auto",
        "forecast_days": days,
    })
    data = _guarded_get(f"{FORECAST_URL}?{params}")
    _store(key, data)
    return data


def search_cities(query: str, count: int = 5) -> dict:
    key = f"geo:{query.lower()}:{count}"
    hit = _cached(key, GEOCODING_CACHE_SECONDS)
    if hit is not None:
        return hit

    params = urlencode({"name": query, "count": count, "language": "en"})
    data = _guarded_get(f"{GEOCODING_URL}?{params}")
    _store(key, data)
    return data


def fetch_archive(latitude: float, longitude: float, start_date: str, end_date: str) -> dict:
    """Historical daily records. Free, and goes back decades.

    This is what makes the timeline useful on day one instead of only after
    the app has been running long enough to accumulate its own observations.
    """
    key = f"archive:{latitude:.3f},{longitude:.3f},{start_date},{end_date}"
    hit = _cached(key, ARCHIVE_CACHE_SECONDS)
    if hit is not None:
        return hit

    params = urlencode({
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "daily": DAILY_FIELDS,
        "timezone": "auto",
    })
    data = _guarded_get(f"{ARCHIVE_URL}?{params}")
    _store(key, data)
    return data


def daily_rows_from_response(data: dict) -> list[dict]:
    """Pivot Open-Meteo's columnar `daily` block into per-date row dicts.

    Open-Meteo returns parallel arrays ({"time": [...], "temperature_2m_max":
    [...]}), not records — so this is the shape adapter between the API and
    upsert_weather_daily(). Missing/short arrays are tolerated: a partial day
    is better than dropping the whole response.
    """
    daily = (data or {}).get("daily") or {}
    dates = daily.get("time") or []

    def col(name: str) -> list:
        values = daily.get(name) or []
        # Pad rather than zip-truncate, so one short column can't silently
        # drop every later date.
        return list(values) + [None] * (len(dates) - len(values))

    tmax = col("temperature_2m_max")
    tmin = col("temperature_2m_min")
    precip = col("precipitation_sum")
    codes = col("weather_code")
    wind = col("wind_speed_10m_max")

    return [
        {
            "date": d,
            "temp_max": tmax[i],
            "temp_min": tmin[i],
            "precipitation_sum": precip[i],
            "weather_code": codes[i],
            "wind_speed_max": wind[i],
        }
        for i, d in enumerate(dates)
    ]
