"""Article Research (Deep Research cache) queries — port of queries.ts:807-874."""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select

from app.db.models import ArticleResearch as ArticleResearchModel
from app.db.session import SessionLocal


@dataclass
class ArticleResearch:
    id: int
    article_id: int
    question: str
    answer: str
    sources: list[dict]
    model: str | None
    created_at: str


def _map_research_row(row: ArticleResearchModel) -> ArticleResearch:
    try:
        sources = json.loads(row.sources or "[]")
    except (json.JSONDecodeError, TypeError):
        sources = []
    return ArticleResearch(
        id=row.id,
        article_id=row.article_id,
        question=row.question,
        answer=row.answer,
        sources=sources,
        model=row.model,
        created_at=row.created_at,
    )


def get_article_research(article_id: int, question: str) -> ArticleResearch | None:
    """Get the most recent cached research answer for a question, if any."""
    with SessionLocal() as db:
        row = db.execute(
            select(ArticleResearchModel)
            .where(
                ArticleResearchModel.article_id == article_id,
                ArticleResearchModel.question == question,
            )
            .order_by(ArticleResearchModel.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        return _map_research_row(row) if row else None


def save_article_research(
    article_id: int,
    question: str,
    answer: str,
    sources: list[dict],
    model: str,
) -> int:
    """Save a research result and return its ID."""
    with SessionLocal() as db:
        research = ArticleResearchModel(
            article_id=article_id,
            question=question,
            answer=answer,
            sources=json.dumps(sources),
            model=model,
        )
        db.add(research)
        db.commit()
        db.refresh(research)
        return research.id


def get_all_article_research(article_id: int) -> list[ArticleResearch]:
    """Get all research history for an article, newest first."""
    with SessionLocal() as db:
        rows = db.execute(
            select(ArticleResearchModel)
            .where(ArticleResearchModel.article_id == article_id)
            .order_by(ArticleResearchModel.created_at.desc())
        ).scalars().all()

        return [_map_research_row(r) for r in rows]


def delete_article_research(research_id: int) -> None:
    """Delete a research entry by ID."""
    with SessionLocal() as db:
        row = db.execute(
            select(ArticleResearchModel).where(ArticleResearchModel.id == research_id)
        ).scalar_one_or_none()
        if row:
            db.delete(row)
            db.commit()
