"""Preferences endpoints — /api/preferences. Port of src/app/api/preferences/route.ts."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.repository import (
    delete_preference_keyword,
    get_category_by_slug,
    get_preference_keywords,
    upsert_preference_keyword,
)
from app.lib.ranking.preferences import rebuild_preferences
from app.lib.server.rate_limit import TEN_MIN_MS, rate_limit
from app.schemas import PreferenceCreateRequestBody, PreferenceRebuildRequestBody

router = APIRouter()


def _reject_unknown_category(category: str) -> None:
    """400 on a category that isn't a real section.

    spec-v0.5 1.4 widened ranking to every category, so this validates against
    the categories table instead of the v0.4 capped list — which would have
    rejected a perfectly valid technology preference.
    """
    if not get_category_by_slug(category):
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")


@router.get(
    "/preferences",
    dependencies=[Depends(rate_limit("preferences-get", 120, TEN_MIN_MS))],
)
async def list_preferences(category: Optional[str] = Query(None)) -> dict:
    category = category.strip() if category else None

    if category:
        _reject_unknown_category(category)

    keywords = get_preference_keywords(category)
    return {"keywords": keywords}


@router.post(
    "/preferences",
    dependencies=[Depends(rate_limit("preferences-post", 60, TEN_MIN_MS))],
)
async def create_preference(body: PreferenceCreateRequestBody) -> dict:
    _reject_unknown_category(body.categorySlug)

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

    if category_slug:
        _reject_unknown_category(category_slug)

    rebuild_preferences(category_slug)
    return {"success": True}
