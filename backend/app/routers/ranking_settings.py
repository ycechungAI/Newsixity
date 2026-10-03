"""Per-category ranking settings — /api/ranking/settings.

One row per section, holding what the refresh stores (§2.9) and what ranking
promotes and scores (§5). Reads always succeed: a section with no row reads
back as the v0.4 defaults, so this surface can never make scoring fail.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.db.repository import (
    DEFAULT_SCORE_WEIGHTS,
    MAX_CAPTURED_FEED_HARD_CAP,
    MAX_PROMOTE_LIMIT,
    SCORE_WEIGHT_KEYS,
    get_all_ranking_settings,
    get_category_by_slug,
    upsert_ranking_settings,
)
from app.db.repository.ranking_settings import (
    DEFAULT_FEED_HARD_CAP,
    DEFAULT_FEED_SOFT_CAP,
)
from app.lib.server.rate_limit import TEN_MIN_MS, rate_limit

router = APIRouter()


class ScoreWeights(BaseModel):
    """The five signals' shares, as percentages summing to 100 (§5.4)."""

    groupSize: int = Field(ge=0, le=100)
    preferenceMatch: int = Field(ge=0, le=100)
    sourceWeight: int = Field(ge=0, le=100)
    recency: int = Field(ge=0, le=100)
    titleImportance: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def check_total(self) -> "ScoreWeights":
        if sum(self.model_dump().values()) != 100:
            raise ValueError(
                "Score weights must add up to 100 (currently "
                f"{sum(self.model_dump().values())})"
            )
        return self

    def as_dict(self) -> dict[str, int]:
        return dict(self.model_dump())


class RankingSettingsBody(BaseModel):
    """A section's settings. Omitted fields keep their stored value."""

    feedSoftCap: int | None = Field(default=None, ge=0, le=MAX_CAPTURED_FEED_HARD_CAP)
    feedHardCap: int | None = Field(default=None, ge=0, le=MAX_CAPTURED_FEED_HARD_CAP)
    promoteLimit: int | None = Field(default=None, ge=1, le=MAX_PROMOTE_LIMIT)
    ranked: bool | None = None
    weights: ScoreWeights | None = None


def _serialize(settings) -> dict:
    return {
        "categorySlug": settings.category_slug,
        "feedSoftCap": settings.feed_soft_cap,
        "feedHardCap": settings.feed_hard_cap,
        "promoteLimit": settings.promote_limit,
        "ranked": settings.ranked,
        "weights": settings.weights,
    }


@router.get(
    "/ranking/settings",
    dependencies=[Depends(rate_limit("ranking-settings-get", 120, TEN_MIN_MS))],
)
async def list_ranking_settings() -> dict:
    """Every section's settings, plus the defaults the UI builds sliders from."""
    return {
        "settings": [_serialize(s) for s in get_all_ranking_settings()],
        "defaults": {
            "feedSoftCap": DEFAULT_FEED_SOFT_CAP,
            "feedHardCap": DEFAULT_FEED_HARD_CAP,
            "weights": DEFAULT_SCORE_WEIGHTS,
        },
    }


@router.put(
    "/ranking/settings/{category_slug}",
    dependencies=[Depends(rate_limit("ranking-settings-put", 60, TEN_MIN_MS))],
)
async def update_ranking_settings(category_slug: str, body: RankingSettingsBody) -> dict:
    if not get_category_by_slug(category_slug):
        raise HTTPException(status_code=404, detail=f"Unknown category '{category_slug}'")

    try:
        settings = upsert_ranking_settings(
            category_slug,
            feed_soft_cap=body.feedSoftCap,
            feed_hard_cap=body.feedHardCap,
            promote_limit=body.promoteLimit,
            ranked=body.ranked,
            weights=body.weights.as_dict() if body.weights else None,
        )
    except ValueError as e:
        # Only raised for weights that don't sum to 100, which ScoreWeights has
        # already rejected — so this is a backstop, not a user-facing path.
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {"success": True, "settings": _serialize(settings)}