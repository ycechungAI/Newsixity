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
from app.db.repository.helpers import Article
from app.lib.dedup.similarity import bigram_similarity, normalize_title_for_hash


def group_articles(articles: list[Article], category_slug: str) -> None:
    """Group new articles with recent similar groups or create new groups.

    For each article:
    - Find the best-matching recent group (by bigram similarity)
    - If score > 0.5, assign to that group and increment count
    - If new article has more content than group representative, promote it
    - Otherwise, create a new group with this article as representative
    """
    for article in articles:
        recent_groups = get_recent_groups_by_category(category_slug, limit=None)

        best_match_group_id = None
        best_match_score = 0.0
        best_match_content = None

        for group in recent_groups:
            score = bigram_similarity(article.title, group.representative.title)

            if score > best_match_score:
                best_match_score = score
                best_match_group_id = group.id
                best_match_content = group.representative.content

        if best_match_group_id is not None and best_match_score > 0.5:
            # Assign to existing group
            assign_article_to_group(article.id, best_match_group_id)
            increment_group_count(best_match_group_id)

            # Update representative if new article has more content
            new_content_length = len(article.content or "")
            existing_content_length = len(best_match_content or "")

            if new_content_length > existing_content_length:
                update_group_representative(best_match_group_id, article.id)
        else:
            # Create a new group with this article as the representative
            normalized_title = normalize_title_for_hash(article.title)
            create_group(category_slug, article.id, normalized_title)
