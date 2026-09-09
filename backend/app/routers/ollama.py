"""Ollama endpoints — /api/ollama/*. Port of src/app/api/ollama/models/route.ts.

The `ollama` Python package is optional: when it is not installed, the app
must still load and everything else works — only Ollama-specific endpoints
report offline. The guarded import mirrors lib/integrations/ollama.py.
"""

try:
    from ollama import AsyncClient
except ImportError:  # ollama not installed — report offline, keep the app running
    AsyncClient = None  # type: ignore[assignment,misc]

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db.repository import get_setting

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
        "host": host,
        "installed": installed_models,
        "suggestions": suggestions,
    }
