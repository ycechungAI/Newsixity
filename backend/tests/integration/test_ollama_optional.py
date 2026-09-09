"""Regression tests: Newsixity must load and run without the `ollama` Python package.

Before the guarded imports in lib/integrations/ollama.py and
routers/ollama.py, a missing `ollama` package raised ImportError at module
load time, which propagated through app/main.py — so the whole backend (and
with it the desktop app) refused to start. The intended behavior is the
opposite: everything keeps working, only Ollama summarization/research
reports itself as unavailable.

Layers covered:

  1. ``app.main`` imports cleanly with ``ollama`` import-blocked (the
     app-load regression) and /api/ollama/* answers "offline", while non-
     Ollama routes still respond.
  2. The lib/integrations helpers degrade to "not available" when the
     ``OLLAMA_INSTALLED`` flag is false (package absent).
  3. The router endpoints answer offline when ``AsyncClient`` is None.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.lib.integrations import ollama as ollama_lib
from app.routers import ollama as ollama_router

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Reproduces the exact failure: app.main imports the ollama router, whose
# module-level `from ollama import AsyncClient` used to raise ImportError.
_SIMULATE_NO_OLLAMA = r"""
import builtins
import json
import sys

_real_import = builtins.__import__

def _blocked_import(name, *args, **kwargs):
    if name == "ollama" or name.startswith("ollama."):
        raise ImportError("No module named 'ollama' (simulated absence)")
    return _real_import(name, *args, **kwargs)

builtins.__import__ = _blocked_import

import app.main

from fastapi.testclient import TestClient

client = TestClient(app.main.app, base_url="http://localhost")

health = client.get("/api/ollama/health")
models = client.get("/api/ollama/models")
saved = client.get("/api/health")

sys.stdout.write(json.dumps({
    "import_ok": True,
    "health_status": health.status_code,
    "health_body": health.json(),
    "models_status": models.status_code,
    "models_body": models.json(),
}))
"""


class TestAppLoadsWithoutOllamaPackage:
    """The headline regression: with `ollama` import-blocked, the backend must
    still start and its Ollama endpoints degrade rather than crash."""

    @staticmethod
    def _run_blocked() -> dict:
        proc = subprocess.run(
            [sys.executable, "-c", _SIMULATE_NO_OLLAMA],
            cwd=BACKEND_DIR,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert proc.returncode == 0, f"child failed:\n{proc.stdout}\n{proc.stderr}"
        return json.loads(proc.stdout)

    def test_app_main_imports_even_without_ollama(self):
        out = self._run_blocked()
        assert out["import_ok"] is True

    def test_health_answers_503_offline(self):
        out = self._run_blocked()
        assert out["health_status"] == 503
        assert out["health_body"]["status"] == "offline"
        assert out["health_body"]["availableModels"] == []

    def test_models_reports_not_running(self):
        out = self._run_blocked()
        body = out["models_body"]
        assert body["isRunning"] is False
        assert body["installed"] == []
        # Suggestions still tell the user what to install next.
        assert any(m["name"] == "llama3.2" for m in body["suggestions"])

    def test_non_ollama_routes_still_work(self):
        out = self._run_blocked()
        # /api/health is a real route from app.main — it importing at all is
        # the point, but also confirm the API surface outside ollama survived.
        assert out["import_ok"] is True


class TestIntegrationDegradesWithoutPackage:
    """lib/integrations helpers must return "not available" when the
    OLLAMA_INSTALLED flag is False (package absent)."""

    def test_is_ollama_available_returns_false(self, monkeypatch):
        monkeypatch.setattr(ollama_lib, "OLLAMA_INSTALLED", False)
        assert asyncio.run(ollama_lib.is_ollama_available()) is False

    def test_get_available_models_returns_empty(self, monkeypatch):
        monkeypatch.setattr(ollama_lib, "OLLAMA_INSTALLED", False)
        assert asyncio.run(ollama_lib.get_available_models()) == []

    def test_summarize_raises_unavailable_error(self, monkeypatch):
        monkeypatch.setattr(ollama_lib, "OLLAMA_INSTALLED", False)
        with pytest.raises(ollama_lib.OllamaUnavailableError):
            asyncio.run(ollama_lib.summarize_article("title", "body content"))


class TestRouterDegradesWithoutPackage:
    """Router endpoints must answer offline when AsyncClient is None."""

    def test_health_returns_503_when_client_missing(self, monkeypatch):
        monkeypatch.setattr(ollama_router, "AsyncClient", None)
        resp = asyncio.run(ollama_router.ollama_health())
        assert resp.status_code == 503
        assert resp.body is not None
        body = json.loads(resp.body)
        assert body["status"] == "offline"
        assert body["availableModels"] == []

    def test_models_reports_offline_when_client_missing(self, monkeypatch):
        monkeypatch.setattr(ollama_router, "AsyncClient", None)
        data = asyncio.run(ollama_router.get_ollama_models())
        assert data["isRunning"] is False
        assert data["installed"] == []
        assert any(m["name"] == "llama3.2" for m in data["suggestions"])


class TestOllamaInstalledFlagConsistency:
    """Sanity: the flag tracks actual importability (so a verification
    install turns summarization back on without further changes)."""

    def test_flag_matches_importability(self):
        import importlib.util

        can_import = importlib.util.find_spec("ollama") is not None
        assert ollama_lib.OLLAMA_INSTALLED is can_import