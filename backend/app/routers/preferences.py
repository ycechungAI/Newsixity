"""Preferences endpoints — /api/preferences. Port of src/app/api/preferences/route.ts."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.repository import (
    CAPPED_CATEGORIES,
    delete_preference_keyword,
    get_preference_keywords,
    upsert_preference_keyword,
)
from app.lib.ranking.preferences import rebuild_preferences
from app.lib.server.rate_limit import TEN_MIN_MS, rate_limit
from app.schemas import PreferenceCreateRequestBody, PreferenceRebuildRequestBody

router = APIRouter()

VALID_CATEGORIES = set(CAPPED_CATEGORIES)


@router.get(
    "/preferences",
    dependencies=[Depends(rate_limit("preferences-get", 120, TEN_MIN_MS))],
)
async def list_preferences(category: Optional[str] = Query(None)) -> dict:
    category = category.strip() if category else None

    if category and category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {', '.join(CAPPED_CATEGORIES)}",
        )

    keywords = get_preference_keywords(category)
    return {"keywords": keywords}


@router.post(
    "/preferences",
    dependencies=[Depends(rate_limit("preferences-post", 60, TEN_MIN_MS))],
)
async def create_preference(body: PreferenceCreateRequestBody) -> dict:
    if body.categorySlug not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {', '.join(CAPPED_CATEGORIES)}",
        )

    upsert_preference_keyword(
        body.categorySlug,
        body.keyword,
        body.weight if body.weight is not None else 1.0,
        body.source or "manual",
    )

    return {"success": True}


@router.delete(
    "/preferences",
    dependencies=[Depends(rate_limit("preferences-delete", 60, TEN_MIN_MS))],
)
async def delete_preference(id: int = Query(..., gt=0)) -> dict:
    delete_preference_keyword(id)
    return {"success": True}


@router.put(
    "/preferences",
    dependencies=[Depends(rate_limit("preferences-put", 30, TEN_MIN_MS))],
)
async def rebuild(body: Optional[PreferenceRebuildRequestBody] = None) -> dict:
    category_slug = body.categorySlug if body else None

    if category_slug and category_slug not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {', '.join(CAPPED_CATEGORIES)}",
        )

    rebuild_preferences(category_slug)
    return {"success": True}
