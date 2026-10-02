"""Daily briefing queries (v0.4 §3)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db.models import DailyBriefing as BriefingModel
from app.db.repository.feeds import MANUAL_FEED_URL
from app.db.session import SessionLocal

@dataclass
class Briefing:
    date: str
    content: str
    sources: list[dict]
    model: str | None
    created_at: str


@dataclass
class BriefingCandidate:
    id: int
    title: str
    text: str
    category_slug: str
    feed_name: str


def get_briefing(date: str) -> Briefing | None:
    with SessionLocal() as db:
        row = db.execute(select(BriefingModel).where(BriefingModel.date == date)).scalar_one_or_none()
        if row is None:
            return None
        try:
            sources = json.loads(row.sources or "[]")
        except ValueError:
            sources = []
        return Briefing(row.date, row.content, sources, row.model, row.created_at)


def save_briefing(date: str, content: str, sources: list[dict], model: str | None) -> None:
    """Insert or replace the briefing for `date` (regenerate overwrites)."""
    values = {"content": content, "sources": json.dumps(sources), "model": model}
    with SessionLocal() as db:
        db.execute(
            sqlite_insert(BriefingModel)
            .values(date=date, **values)
            .on_conflict_do_update(
                index_elements=["date"],
                set_={**values, "created_at": func.datetime("now")},
            )
        )
        db.commit()


def list_briefing_dates(limit: int = 30) -> list[str]:
    with SessionLocal() as db:
        return list(
            db.execute(
                select(BriefingModel.date).order_by(BriefingModel.date.desc()).limit(limit)
            ).scalars()
        )


def get_briefing_candidates(
    since_utc: str, until_utc: str, limit: int = 20, per_category: int = 4
) -> list[BriefingCandidate]:
    """The day's top-ranked articles, spread across categories.

    Ranked by the existing scorer's output (promoted first, then
    relevance_score), capped per category so one busy category can't fill
    the whole briefing. Manual Links is excluded, as the summarizer does —
    a briefing about the user's own saved links is noise. The window
    [since_utc, until_utc) is compared against fetched_at, which SQLite
    stores as UTC "YYYY-MM-DD HH:MM:SS" text.
    """
    sql = text(
        """
        SELECT id, title, summary, content, category_slug, feed_name FROM (
            SELECT a.id, a.title, a.summary, a.content, c.slug AS category_slug,
                   f.name AS feed_name, a.is_promoted, a.relevance_score,
                   ROW_NUMBER() OVER (
                       PARTITION BY c.id
                       ORDER BY a.is_promoted DESC, a.relevance_score DESC, a.id DESC
                   ) AS rank_in_category
            FROM articles a
            JOIN feeds f ON a.feed_id = f.id
            JOIN categories c ON f.category_id = c.id
            WHERE a.fetched_at >= :since AND a.fetched_at < :until
              AND f.url != :manual
              AND c.slug != 'weather'  -- a dashboard, not news
        )
        WHERE rank_in_category <= :per_category
        ORDER BY is_promoted DESC, relevance_score DESC, id DESC
        LIMIT :limit
        """
    )
    with SessionLocal() as db:
        rows = db.execute(
            sql,
            {"since": since_utc, "until": until_utc, "manual": MANUAL_FEED_URL, "per_category": per_category, "limit": limit},
        ).mappings().all()

    candidates = []
    for r in rows:
        summary = r["summary"] or ""
        # Placeholder summaries ("[Skipped: ...]") are bookkeeping, not news.
        body = summary if summary and not summary.startswith("[") else (r["content"] or "")[:400]
        candidates.append(
            BriefingCandidate(r["id"], r["title"], body.strip(), r["category_slug"], r["feed_name"])
        )
    return candidates
