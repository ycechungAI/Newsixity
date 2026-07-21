"""Settings endpoints — /api/settings. Port of src/app/api/settings/route.ts."""

from fastapi import APIRouter, HTTPException

from app.db.repository import (
    get_all_settings,
    get_ollama_model_setting,
    set_ollama_model_setting,
    set_setting,
    SettingsEncryptionRequiredError,
)
from app.schemas import SettingsUpdateRequestBody

router = APIRouter()

DEFAULT_MODEL = "granite4.1:8b"


def _mask_api_key(key: str) -> str:
    if len(key) > 4:
        return "•" * (len(key) - 4) + key[-4:]
    return "•" * len(key)


@router.get("/settings")
async def get_settings() -> dict:
    settings = get_all_settings()

    effective_model = get_ollama_model_setting() or DEFAULT_MODEL
    settings["ollama_model"] = effective_model

    api_key = settings.get("brave_search_api_key")
    if api_key:
        settings["brave_search_api_key"] = _mask_api_key(api_key)

    return {
        "settings": {
            "brave_search_api_key": settings.get("brave_search_api_key") or "",
            "ollama_model": settings.get("ollama_model") or DEFAULT_MODEL,
            "ollama_host": settings.get("ollama_host") or "http://localhost:11434",
        }
    }


@router.post("/settings")
async def update_settings(body: SettingsUpdateRequestBody) -> dict:
    try:
        if body.brave_search_api_key is not None:
            # A masked key (contains the bullet mask char) means "unchanged" — don't overwrite.
            if "•" not in body.brave_search_api_key:
                set_setting("brave_search_api_key", body.brave_search_api_key or None)

        if body.ollama_model is not None:
            set_ollama_model_setting(body.ollama_model or DEFAULT_MODEL)

        if body.ollama_host is not None:
            set_setting("ollama_host", body.ollama_host or "http://localhost:11434")
    except SettingsEncryptionRequiredError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {"success": True, "message": "Settings saved successfully"}
