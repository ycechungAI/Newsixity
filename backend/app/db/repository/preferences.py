"""User preference (keyword weighting) queries — port of queries.ts:1836-1903."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import case, delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db.models import UserPreference as UserPreferenceModel
from app.db.session import SessionLocal


@dataclass
class UserPreference:
    id: int
    category_slug: str
    keyword: str
    weight: float
    source: str
    updated_at: str


def get_preference_keywords(category_slug: str | None = None) -> list[UserPreference]:
    with SessionLocal() as db:
        query = select(UserPreferenceModel)

        if category_slug:
            query = query.where(UserPreferenceModel.category_slug == category_slug).order_by(
                UserPreferenceModel.weight.desc()
            )
        else:
            query = query.order_by(
                UserPreferenceModel.category_slug, UserPreferenceModel.weight.desc()
            )

        rows = db.execute(query).scalars().all()
        return [
            UserPreference(
                id=r.id,
                category_slug=r.category_slug,
                keyword=r.keyword,
                weight=r.weight,
                source=r.source,
                updated_at=r.updated_at,
            )
            for r in rows
        ]


def upsert_preference_keyword(
    category_slug: str,
    keyword: str,
    weight: float,
    source: str = "auto",
) -> None:
    """Insert or update a preference keyword's weight.

    Matches queries.ts's CASE logic exactly: an existing 'manual' source is
    never downgraded back to 'auto' by a subsequent auto-learned update, but
    a new 'manual' write always wins.
    """
    with SessionLocal() as db:
        keyword_lower = keyword.lower()

        stmt = sqlite_insert(UserPreferenceModel).values(
            category_slug=category_slug,
            keyword=keyword_lower,
            weight=weight,
            source=source,
            updated_at=func.datetime("now"),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["category_slug", "keyword"],
            set_={
                "weight": stmt.excluded.weight,
                "source": case(
                    (stmt.excluded.source == "manual", "manual"),
                    else_=UserPreferenceModel.source,
                ),
                "updated_at": func.datetime("now"),
            },
        )
        db.execute(stmt)
        db.commit()


def delete_preference_keyword(preference_id: int) -> None:
    with SessionLocal() as db:
        db.execute(delete(UserPreferenceModel).where(UserPreferenceModel.id == preference_id))
        db.commit()


def clear_auto_preferences(category_slug: str | None = None) -> None:
    with SessionLocal() as db:
        query = delete(UserPreferenceModel).where(UserPreferenceModel.source == "auto")
        if category_slug:
            query = query.where(UserPreferenceModel.category_slug == category_slug)
        db.execute(query)
        db.commit()
