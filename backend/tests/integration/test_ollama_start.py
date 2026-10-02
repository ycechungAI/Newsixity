"""POST /api/ollama/start and the binaryInstalled flag (v0.4 §0.1).

The frontend's OllamaStartPrompt read both before either existed, so the
prompt could never open and its button would have 404'd into a JSON parse.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import ollama as ollama_router


@pytest.fixture
def client():
    return TestClient(app, base_url="http://localhost")


@pytest.fixture
def spawned(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(ollama_router, "_spawn_ollama_serve", lambda b: calls.append(b))
    return calls


def _running(value):
    async def check(_host):
        return value() if callable(value) else value
    return check


class TestStartOllama:
    def test_already_running_is_success_without_spawning(self, client, monkeypatch, spawned):
        monkeypatch.setattr(ollama_router, "_is_running", _running(True))
        r = client.post("/api/ollama/start")
        assert r.status_code == 200 and r.json()["success"] is True
        assert spawned == []

    def test_remote_host_is_refused(self, client, monkeypatch, spawned):
        monkeypatch.setattr(ollama_router, "_is_running", _running(False))
        monkeypatch.setattr(ollama_router, "_host", lambda: "http://10.0.0.5:11434")
        r = client.post("/api/ollama/start")
        assert r.status_code == 400 and r.json()["success"] is False
        assert spawned == []

    def test_missing_binary_is_404(self, client, monkeypatch, spawned):
        monkeypatch.setattr(ollama_router, "_is_running", _running(False))
        monkeypatch.setattr(ollama_router, "_host", lambda: "http://localhost:11434")
        monkeypatch.setattr(ollama_router, "find_ollama_binary", lambda: None)
        r = client.post("/api/ollama/start")
        assert r.status_code == 404
        assert spawned == []

    @pytest.mark.skipif(ollama_router.AsyncClient is None, reason="ollama package absent")
    def test_spawns_detected_binary_and_waits_until_up(self, client, monkeypatch, spawned):
        state = {"n": 0}

        def up():
            state["n"] += 1
            return state["n"] > 2  # down on the pre-check, up on the first poll

        monkeypatch.setattr(ollama_router, "_is_running", _running(up))
        monkeypatch.setattr(ollama_router, "_host", lambda: "http://127.0.0.1:11434")
        monkeypatch.setattr(ollama_router, "find_ollama_binary", lambda: "/opt/x/ollama")
        r = client.post("/api/ollama/start")
        assert r.status_code == 200 and r.json()["success"] is True
        assert spawned == ["/opt/x/ollama"]


class TestModelsReportsBinary:
    def test_binary_installed_field_present(self, client, monkeypatch):
        monkeypatch.setattr(ollama_router, "find_ollama_binary", lambda: "/usr/local/bin/ollama")
        body = client.get("/api/ollama/models").json()
        assert body["binaryInstalled"] is True
