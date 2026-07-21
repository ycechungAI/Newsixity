"""Categories endpoint — /api/categories."""

from fastapi import APIRouter

from app.db.repository import get_categories, get_article_count_by_category
from app.schemas import CategoryWithCounts

router = APIRouter()


@router.get("/categories", response_model=list[CategoryWithCounts])
async def list_categories() -> list[CategoryWithCounts]:
    """Get all categories with article counts."""
    categories = get_categories()
    counts = get_article_count_by_category()

    # Build a lookup map from slug to counts.
    # get_article_count_by_category() returns list[dict], so index by key.
    count_map = {c["slug"]: {"total": c["total"], "unread": c["unread"]} for c in counts}

    # Merge counts into category objects
    result = []
    for cat in categories:
        count = count_map.get(cat.slug, {"total": 0, "unread": 0})
        result.append(
            CategoryWithCounts(
                id=cat.id,
                name=cat.name,
                slug=cat.slug,
                sort_order=cat.sort_order,
                total=count["total"],
                unread=count["unread"],
            )
        )

    return result
