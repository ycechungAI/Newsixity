"""Category queries."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Category as CategoryModel
from app.db.repository.helpers import Category
from app.db.session import SessionLocal


def get_categories() -> list[Category]:
    """Get all categories ordered by sort_order."""
    with SessionLocal() as db:
        rows = db.execute(
            select(CategoryModel).order_by(CategoryModel.sort_order)
        ).scalars().all()
        return [
            Category(
                id=r.id,
                name=r.name,
                slug=r.slug,
                sort_order=r.sort_order,
            )
            for r in rows
        ]


def get_category_by_slug(slug: str) -> Category | None:
    """Get a category by its slug."""
    with SessionLocal() as db:
        row = db.execute(
            select(CategoryModel).where(CategoryModel.slug == slug)
        ).scalar_one_or_none()
        if not row:
            return None
        return Category(
            id=row.id,
            name=row.name,
            slug=row.slug,
            sort_order=row.sort_order,
        )
