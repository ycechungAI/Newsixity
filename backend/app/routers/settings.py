"""Settings endpoints — /api/settings. Port of src/app/api/settings/route.ts."""

from fastapi import APIRouter, Depends, HTTPException

from app.db.repository import (
    get_all_settings,
    get_ollama_model_setting,
    set_ollama_model_setting,
    set_setting,
    SettingsEncryptionRequiredError,
)
from app.lib.integrations.ollama import get_available_models
from app.lib.server.rate_limit import TEN_MIN_MS, rate_limit
from app.lib.services.summarization import get_default_model
from app.schemas import SettingsUpdateRequestBody

router = APIRouter()


def _mask_api_key(key: str) -> str:
    if len(key) > 4:
        return "•" * (len(key) - 4) + key[-4:]
    return "•" * len(key)


@router.get(
    "/settings",
    dependencies=[Depends(rate_limit("settings-get", 120, TEN_MIN_MS))],
)
async def get_settings() -> dict:
    settings = get_all_settings()

    stored_model = get_ollama_model_setting()
    effective_model = stored_model

    # If a model is stored but doesn't exist in Ollama, use dynamic default instead.
    if stored_model:
        try:
            available = await get_available_models()
            if stored_model not in available:
                effective_model = await get_default_model()
        except Exception:
            # If we can't query Ollama, fall back to stored model (might still work).
            pass
    else:
        effective_model = await get_default_model()

    api_key = settings.get("brave_search_api_key")
    if api_key:
        settings["brave_search_api_key"] = _mask_api_key(api_key)

    return {
        "settings": {
            "brave_search_api_key": settings.get("brave_search_api_key") or "",
            "ollama_model": effective_model,
            "ollama_host": settings.get("ollama_host") or "http://localhost:11434",
        }
    }


@router.post(
    "/settings",
    dependencies=[Depends(rate_limit("settings-post", 60, TEN_MIN_MS))],
)
async def update_settings(body: SettingsUpdateRequestBody) -> dict:
    try:
        if body.brave_search_api_key is not None:
            # A masked key (contains the bullet mask char) means "unchanged" — don't overwrite.
            if "•" not in body.brave_search_api_key:
                set_setting("brave_search_api_key", body.brave_search_api_key or None)

        if body.ollama_model is not None:
            set_ollama_model_setting(body.ollama_model or "")

        if body.ollama_host is not None:
            set_setting("ollama_host", body.ollama_host or "http://localhost:11434")
    except SettingsEncryptionRequiredError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {"success": True, "message": "Settings saved successfully"}
