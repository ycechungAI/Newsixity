"""Article deduplication via title similarity and grouping."""

from app.lib.dedup.similarity import (
    normalize_title_for_hash,
    hash_title,
    get_bigrams,
    bigram_similarity,
    is_duplicate,
)
from app.lib.dedup.grouping import group_articles

__all__ = [
    "normalize_title_for_hash",
    "hash_title",
    "get_bigrams",
    "bigram_similarity",
    "is_duplicate",
    "group_articles",
]
