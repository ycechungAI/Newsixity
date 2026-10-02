"""Ollama endpoints — /api/ollama/*. Port of src/app/api/ollama/models/route.ts.

The `ollama` Python package is optional: when it is not installed, the app
must still load and everything else works — only Ollama-specific endpoints
report offline. The guarded import mirrors lib/integrations/ollama.py.
"""

import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    from ollama import AsyncClient
except ImportError:  # ollama not installed — report offline, keep the app running
    AsyncClient = None  # type: ignore[assignment,misc]

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.db.repository import get_setting
from app.lib.server.rate_limit import TEN_MIN_MS, rate_limit

router = APIRouter()

SUGGESTED_MODELS = [
    {
        "name": "llama3.2",
        "size": "2GB",
        "description": "Fast, efficient model for general tasks",
        "recommended": True,
    },
    {
        "name": "llama3.2:3b",
        "size": "2GB",
        "description": "Compact 3B model, very fast",
        "recommended": False,
    },
    {
        "name": "llama3.1:8b",
        "size": "4.7GB",
        "description": "More capable 8B model, good balance",
        "recommended": False,
    },
    {
        "name": "qwen2.5:7b",
        "size": "4.7GB",
        "description": "Strong multilingual model",
        "recommended": False,
    },
    {
        "name": "mistral:7b",
        "size": "4.1GB",
        "description": "Popular, high quality model",
        "recommended": False,
    },
]


# The desktop sidecar is launched by Tauri, not a login shell, so PATH often
# lacks Homebrew and friends — check the standard install locations as well.
_OLLAMA_CANDIDATES = [
    "/usr/local/bin/ollama",
    "/opt/homebrew/bin/ollama",
    "/Applications/Ollama.app/Contents/Resources/ollama",
    "/usr/bin/ollama",
    str(Path.home() / ".local/bin/ollama"),
]
if sys.platform == "win32":
    _OLLAMA_CANDIDATES.append(
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Ollama/ollama.exe")
    )

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
START_TIMEOUT_SECONDS = 10.0


def find_ollama_binary() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    for candidate in _OLLAMA_CANDIDATES:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _host() -> str:
    return get_setting("ollama_host") or "http://localhost:11434"


async def _is_running(host: str) -> bool:
    if AsyncClient is None:
        return False
    try:
        await AsyncClient(host=host).list()
        return True
    except Exception:
        return False


def _spawn_ollama_serve(binary: str) -> None:
    """Start `ollama serve` detached from this process.

    Fixed argv, no shell: nothing from the request reaches the command line.
    Detached so the server outlives a backend restart, like the user starting
    it themselves would.
    """
    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        )
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen([binary, "serve"], **kwargs)  # noqa: S603


@router.post(
    "/ollama/start",
    dependencies=[Depends(rate_limit("ollama-start", 10, TEN_MIN_MS))],
)
async def start_ollama() -> JSONResponse:
    """Start the local Ollama server for the OllamaStartPrompt dialog.

    Only for a local host: if the user pointed Newsixity at Ollama on another
    machine, starting a process here would not make that one reachable.
    """
    host = _host()
    if await _is_running(host):
        return JSONResponse({"success": True, "message": "Ollama is already running."})

    if (urlparse(host).hostname or "") not in _LOCAL_HOSTS:
        return JSONResponse(
            {"success": False, "message": f"Ollama is configured at {host}, which is not this computer — start it there."},
            status_code=400,
        )
    if AsyncClient is None:
        return JSONResponse(
            {"success": False, "message": "The 'ollama' Python package is not installed in this build."},
            status_code=503,
        )
    binary = find_ollama_binary()
    if binary is None:
        return JSONResponse(
            {"success": False, "message": "Ollama is not installed. Get it from https://ollama.com/download."},
            status_code=404,
        )

    try:
        await asyncio.to_thread(_spawn_ollama_serve, binary)
    except OSError as e:
        return JSONResponse(
            {"success": False, "message": f"Could not start Ollama: {e}"}, status_code=500
        )

    deadline = asyncio.get_running_loop().time() + START_TIMEOUT_SECONDS
    while asyncio.get_running_loop().time() < deadline:
        if await _is_running(host):
            return JSONResponse({"success": True, "message": "Ollama started."})
        await asyncio.sleep(0.5)
    return JSONResponse(
        {"success": False, "message": "Ollama was launched but did not answer within 10 seconds."},
        status_code=504,
    )


@router.get("/ollama/health")
async def ollama_health() -> JSONResponse:
    """Liveness probe for the Ollama service, with the installed model names.

    Distinct from /ollama/models, which always answers 200 and reports
    reachability in an `isRunning` field. This one signals with the status
    code — 200 up, 503 down — which is what a health probe is for.

    Added because components/settings/OllamaModelSelector.tsx already called
    it and no such route existed: the static catch-all answered with the
    SPA's index.html at status 200, so the component read "online" from an
    HTML page and then found no models.
    """
    host = get_setting("ollama_host") or "http://localhost:11434"
    if AsyncClient is None:
        return JSONResponse(
            {"status": "offline", "host": host, "availableModels": []},
            status_code=503,
        )
    try:
        response = await AsyncClient(host=host).list()
        models = [m.model for m in response.models if m.model]
    except Exception:
        return JSONResponse(
            {"status": "offline", "host": host, "availableModels": []},
            status_code=503,
        )

    return JSONResponse({"status": "online", "host": host, "availableModels": models})


@router.get("/ollama/models")
async def get_ollama_models() -> dict:
    host = get_setting("ollama_host") or "http://localhost:11434"

    installed_models: list[dict] = []
    is_running = False

    if AsyncClient is not None:
        client = AsyncClient(host=host)

        try:
            response = await client.list()
            installed_models = [
                {"name": m.model, "size": m.size, "modified": m.modified_at}
                for m in response.models
            ]
            is_running = True
        except Exception:
            pass

    installed_names = [m["name"] for m in installed_models if m["name"]]

    suggestions = [
        {
            **model,
            "installed": any(
                name.startswith(model["name"].split(":")[0]) for name in installed_names
            ),
        }
        for model in SUGGESTED_MODELS
    ]

    return {
        "isRunning": is_running,
        # Lets the UI offer "Start Ollama" only when there is something to start.
        "binaryInstalled": find_ollama_binary() is not None,
        "host": host,
        "installed": installed_models,
        "suggestions": suggestions,
    }
