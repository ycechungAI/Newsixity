"""Ollama endpoints — /api/ollama/*. Port of src/app/api/ollama/models/route.ts."""

from ollama import AsyncClient

from fastapi import APIRouter

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


@router.get("/ollama/models")
async def get_ollama_models() -> dict:
    host = get_setting("ollama_host") or "http://localhost:11434"
    client = AsyncClient(host=host)

    installed_models: list[dict] = []
    is_running = False

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
