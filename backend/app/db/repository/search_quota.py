"""Search quota queries — port of queries.ts:876-953.

Monthly quota tracking for external search API usage (e.g. Brave Search).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, update

from app.db.models import SearchQuota as SearchQuotaModel
from app.db.session import SessionLocal

MONTHLY_QUOTA_LIMIT = 1900


@dataclass
class SearchQuota:
    id: int
    month_key: str
    query_count: int
    created_at: str
    updated_at: str


def _current_month_key() -> str:
    """Matches TS getCurrentMonthKey(): local-time YYYY-MM."""
    now = datetime.now()
    return f"{now.year:04d}-{now.month:02d}"


def get_monthly_quota() -> SearchQuota:
    """Get (or lazily create) the quota record for the current month."""
    month_key = _current_month_key()

    with SessionLocal() as db:
        row = db.execute(
            select(SearchQuotaModel).where(SearchQuotaModel.month_key == month_key)
        ).scalar_one_or_none()

        if not row:
            row = SearchQuotaModel(month_key=month_key, query_count=0)
            db.add(row)
            db.commit()
            db.refresh(row)

        return SearchQuota(
            id=row.id,
            month_key=row.month_key,
            query_count=row.query_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


def increment_quota() -> int:
    """Increment the current month's query counter and return the new count."""
    month_key = _current_month_key()

    # Ensure the record exists first (mirrors TS calling getMonthlyQuota()).
    get_monthly_quota()

    with SessionLocal() as db:
        db.execute(
            update(SearchQuotaModel)
            .where(SearchQuotaModel.month_key == month_key)
            .values(
                query_count=SearchQuotaModel.query_count + 1,
                updated_at=func.datetime("now"),
            )
        )
        db.commit()

    return get_monthly_quota().query_count


def is_quota_exceeded() -> bool:
    return get_monthly_quota().query_count >= MONTHLY_QUOTA_LIMIT


def get_remaining_quota() -> int:
    return max(0, MONTHLY_QUOTA_LIMIT - get_monthly_quota().query_count)
