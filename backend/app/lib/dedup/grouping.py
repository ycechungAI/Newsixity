"""Article grouping for deduplication — port of src/lib/dedup/grouping.ts.

Uses the repository layer for DB access instead of raw queries.
"""

from app.db.repository.article_groups import (
    get_recent_groups_by_category,
    assign_article_to_group,
    create_group,
    update_group_representative,
    increment_group_count,
)
from app.db.repository.categories import get_category_by_slug
from app.db.repository.helpers import Article
from app.lib.dedup.similarity import bigram_similarity


def group_articles(articles: list[Article], category_slug: str) -> None:
    """Group new articles with recent similar groups or create new groups.

    For each article:
    - Find the best-matching recent group (by bigram similarity)
    - If score > 0.5, assign to that group and increment count
    - If new article has more content than group representative, promote it
    - Otherwise, create a new group with this article as the representative

    This had never run in the Python port: it called the repository with a
    `limit` kwarg it doesn't take, read groups as objects when they are
    dicts, and passed create_group's arguments in the wrong order. The
    TypeError was swallowed into the refresh's error list, so no topic group
    was ever created and the Topics view had nothing to group by.
    """
    category = get_category_by_slug(category_slug)
    if category is None:
        return

    for article in articles:
        recent_groups = get_recent_groups_by_category(category_slug)

        best_match = None
        best_match_score = 0.0
        for group in recent_groups:
            score = bigram_similarity(article.title, group["representative_title"] or "")
            if score > best_match_score:
                best_match_score = score
                best_match = group

        if best_match is not None and best_match_score > 0.5:
            assign_article_to_group(article.id, best_match["id"])
            increment_group_count(best_match["id"])

            # Promote the new article if it has more content than the representative.
            if len(article.content or "") > len(best_match["representative_content"] or ""):
                update_group_representative(best_match["id"], article.id)
        else:
            # Labels come later (Ollama); a singleton group needs none.
            group_id = create_group(None, category.id, article.id)
            assign_article_to_group(article.id, group_id)
