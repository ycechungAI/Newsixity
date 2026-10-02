"""Hourly weather job (v0.4 §4): records every saved city, best-effort."""

from __future__ import annotations

from types import SimpleNamespace

from app.lib.scheduler import weather as job


def test_records_each_city_and_survives_a_failure(monkeypatch):
    cities = [SimpleNamespace(id=1, name="Oslo", latitude=59.9, longitude=10.7),
              SimpleNamespace(id=2, name="Down", latitude=0.0, longitude=0.0),
              SimpleNamespace(id=3, name="Lima", latitude=-12.0, longitude=-77.0)]
    recorded, retention = [], []

    def forecast(lat, lon):
        if lat == 0.0:
            raise TimeoutError("unreachable")
        return {"current": {"temperature_2m": 10.0}, "daily": {}}

    monkeypatch.setattr(job, "list_weather_locations", lambda: cities)
    monkeypatch.setattr(job, "fetch_forecast", forecast)
    monkeypatch.setattr(job, "add_weather_observation", lambda **kw: recorded.append(kw["location_id"]))
    monkeypatch.setattr(job, "delete_old_weather_observations", lambda: retention.append("obs"))
    monkeypatch.setattr(job, "delete_old_weather_daily", lambda: retention.append("daily"))

    assert job._record_all_sync() == (2, 1)
    assert recorded == [1, 3]
    assert retention == ["obs", "daily"]


def test_job_is_scheduled():
    import inspect

    from app.lib.scheduler import service

    assert "weather-hourly" in inspect.getsource(service.start_background_services)
