"""/api/briefing routes (v0.4 §3)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.lib.scheduler import briefing as service
from app.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(service, "_generating", None)
    monkeypatch.setattr(service, "_last_error", {})
    return TestClient(app, base_url="http://localhost")


def test_missing_briefing_is_a_plain_state_not_404(client):
    r = client.get("/api/briefing", params={"date": "2001-01-01"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "missing" and body["content"] is None


def test_future_and_malformed_dates_rejected(client):
    assert client.get("/api/briefing", params={"date": "2999-01-01"}).status_code == 422
    assert client.get("/api/briefing", params={"date": "tomorrow"}).status_code == 422


def test_regenerate_claims_then_reports_busy(client, monkeypatch):
    started = []

    async def fake_run(day):
        started.append(day)
        return "generated"  # deliberately keeps the claim, as if still running

    monkeypatch.setattr(service, "run_claimed_generation", fake_run)
    r = client.post("/api/briefing/regenerate", params={"date": "2001-01-01"})
    assert r.status_code == 202 and r.json()["status"] == "generating"
    assert client.get("/api/briefing", params={"date": "2001-01-01"}).json()["status"] == "generating"
    assert client.post("/api/briefing/regenerate").status_code == 409


def test_dates_listing(client):
    assert isinstance(client.get("/api/briefing/dates").json()["dates"], list)
