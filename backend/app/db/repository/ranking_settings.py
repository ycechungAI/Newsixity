"""Per-section ranking settings (spec-v0.5 §5).

Reads never touch a row that doesn't exist: a category with no settings row
gets the documented defaults, which are v0.4's behaviour. That is deliberate —
a fresh install and an upgraded install must score identically (spec §5.3),
and it means the table can be dropped from the picture without changing any
scores.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db.models import RankingSetting as RankingSettingModel
from app.db.repository.ranking import (
    CAPPED_CATEGORIES,
    DEFAULT_SCORE_WEIGHTS,
    DAILY_ARTICLE_LIMIT,
)
from app.db.session import SessionLocal

# Per-feed daily insert caps. spec-v0.5 2.9: these replace the module
# constants in app/lib/scheduler/refresh.py as the *defaults*; the refresh
# itself reads whatever the settings say, so this file is the single source.
DEFAULT_FEED_SOFT_CAP = 5
DEFAULT_FEED_HARD_CAP = 8

# Bounds, so a settings write cannot produce a section that stores nothing or
# one that stores without limit. Deliberately wide — these are a sanity net
# against a bad request, not the policy.
MIN_CAPTURED_FEED_CAP = 0
MAX_CAPTURED_FEED_HARD_CAP = 100
MIN_PROMOTE_LIMIT = 1
MAX_PROMOTE_LIMIT = 500

# Column -> the SCORE_WEIGHT_KEYS name used everywhere else (schema, scorer,
# UI). One mapping so the snake_case storage and the camelCase contract can't
# drift.
_WEIGHT_COLUMNS: dict[str, str] = {
    "groupSize": "weight_group_size",
    "preferenceMatch": "weight_preference_match",
    "sourceWeight": "weight_source_weight",
    "recency": "weight_recency",
    "titleImportance": "weight_title_importance",
}


@dataclass(frozen=True)
class RankingSettings:
    """One section's ranking configuration."""

    category_slug: str
    feed_soft_cap: int
    feed_hard_cap: int
    promote_limit: int
    ranked: bool
    weights: dict[str, int]


def _defaults(category_slug: str) -> RankingSettings:
    return RankingSettings(
        category_slug=category_slug,
        feed_soft_cap=DEFAULT_FEED_SOFT_CAP,
        feed_hard_cap=DEFAULT_FEED_HARD_CAP,
        promote_limit=DAILY_ARTICLE_LIMIT,
        # Matches what _seed_ranking_settings writes: ranked for the sections
        # v0.4 capped, unranked for the rest.
        ranked=category_slug in CAPPED_CATEGORIES,
        weights=dict(DEFAULT_SCORE_WEIGHTS),
    )


def _from_row(row: RankingSettingModel) -> RankingSettings:
    weights = {key: getattr(row, col) for key, col in _WEIGHT_COLUMNS.items()}
    # A row written before a weight column existed, or hand-edited into
    # nonsense, must not be able to produce a scorer that returns nothing.
    if sum(weights.values()) != 100:
        weights = dict(DEFAULT_SCORE_WEIGHTS)
    return RankingSettings(
        category_slug=row.category_slug,
        feed_soft_cap=row.feed_soft_cap,
        feed_hard_cap=row.feed_hard_cap,
        promote_limit=row.promote_limit,
        ranked=bool(row.ranked),
        weights=weights,
    )


def get_ranking_settings(category_slug: str) -> RankingSettings:
    """One section's settings, or the defaults when it has no row."""
    with SessionLocal() as db:
        row = db.execute(
            select(RankingSettingModel).where(
                RankingSettingModel.category_slug == category_slug
            )
        ).scalar_one_or_none()
        return _defaults(category_slug) if row is None else _from_row(row)


def get_all_ranking_settings() -> list[RankingSettings]:
    """Every stored settings row, ordered by category slug."""
    with SessionLocal() as db:
        rows = db.execute(
            select(RankingSettingModel).order_by(RankingSettingModel.category_slug)
        ).scalars().all()
        return [_from_row(r) for r in rows]


def upsert_ranking_settings(
    category_slug: str,
    *,
    feed_soft_cap: int | None = None,
    feed_hard_cap: int | None = None,
    promote_limit: int | None = None,
    ranked: bool | None = None,
    weights: dict[str, int] | None = None,
) -> RankingSettings:
    """Create or update one section's settings; unspecified fields are kept.

    Normalises the soft/hard relationship on write rather than at read time: a
    soft cap above the hard cap would otherwise read back as a feed that can
    never insert anything, and the user would have no way to see why.
    """
    current = get_ranking_settings(category_slug)

    new_soft = current.feed_soft_cap if feed_soft_cap is None else feed_soft_cap
    new_hard = current.feed_hard_cap if feed_hard_cap is None else feed_hard_cap
    if new_soft > new_hard:
        new_soft = new_hard

    new_weights = dict(current.weights)
    if weights:
        new_weights.update(weights)
    if sum(new_weights.values()) != 100:
        # Refuse rather than silently rescale: a caller that hands us weights
        # summing to 95 has a bug, and quietly fixing it here would hide it.
        raise ValueError("Score weights must sum to 100")

    values = {
        "feed_soft_cap": new_soft,
        "feed_hard_cap": new_hard,
        "promote_limit": current.promote_limit if promote_limit is None else promote_limit,
        "ranked": int(current.ranked if ranked is None else ranked),
    }
    for key, col in _WEIGHT_COLUMNS.items():
        values[col] = new_weights[key]

    with SessionLocal() as db:
        stmt = (
            sqlite_insert(RankingSettingModel)
            .values(category_slug=category_slug, **values)
            .on_conflict_do_update(
                index_elements=["category_slug"],
                set_={**values, "updated_at": sqlite_insert(RankingSettingModel).excluded.updated_at},
            )
        )
        db.execute(stmt)
        db.commit()

    return get_ranking_settings(category_slug)