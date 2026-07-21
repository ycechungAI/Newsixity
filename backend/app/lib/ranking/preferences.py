"""Preference-keyword learning — port of src/lib/ranking/preferences.ts.

Extracts keywords from saved-article titles to build a per-category weighted
keyword profile, used to score how well new articles match user interests.
"""

from __future__ import annotations

import re
import time

from app.db.repository import (
    CAPPED_CATEGORIES,
    clear_auto_preferences,
    get_preference_keywords,
    get_saved_articles,
    upsert_preference_keyword,
)

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "need", "dare",
    "ought", "used", "it", "its", "not", "no", "nor", "so", "too", "very",
    "just", "about", "above", "after", "again", "all", "also", "am", "any",
    "because", "before", "between", "both", "each", "few", "get", "got",
    "he", "her", "here", "him", "his", "how", "i", "if", "into", "me",
    "more", "most", "my", "new", "now", "off", "old", "only", "other",
    "our", "out", "over", "own", "re", "s", "same", "she", "some", "such",
    "t", "than", "that", "their", "them", "then", "there", "these", "they",
    "this", "those", "through", "under", "up", "us", "we", "what", "when",
    "where", "which", "while", "who", "whom", "why", "you", "your",
    "says", "said", "say", "report", "reports", "according", "first",
    "last", "make", "makes", "made", "take", "takes", "year", "years",
    "day", "days", "week", "weeks", "month", "months", "time", "people",
    "one", "two", "three", "way", "back", "even", "still", "after",
    "much", "many", "well", "set", "going", "being", "put",
}

_NON_WORD_RE = re.compile(r"[^\w\s-]")


class WeightedKeyword:
    __slots__ = ("keyword", "weight")

    def __init__(self, keyword: str, weight: float):
        self.keyword = keyword
        self.weight = weight


def _extract_keywords(title: str) -> list[str]:
    cleaned = _NON_WORD_RE.sub("", title.lower())
    return [w for w in cleaned.split() if len(w) > 2 and w not in STOP_WORDS]


def rebuild_preferences(category_slug: str | None = None) -> None:
    """Rebuild the auto-generated preference keywords from saved articles.

    Manual keywords (source="manual") are preserved — clear_auto_preferences
    only touches source="auto" rows.
    """
    categories = [category_slug] if category_slug else CAPPED_CATEGORIES

    for slug in categories:
        saved = get_saved_articles(limit=500, category_slug=slug)

        if not saved:
            clear_auto_preferences(slug)
            continue

        keyword_counts: dict[str, int] = {}
        for article in saved:
            for kw in set(_extract_keywords(article.title)):
                keyword_counts[kw] = keyword_counts.get(kw, 0) + 1

        clear_auto_preferences(slug)

        max_count = max(keyword_counts.values(), default=1)
        min_occurrences = 1 if len(saved) < 3 else 2

        for keyword, count in keyword_counts.items():
            if count >= min_occurrences:
                weight = count / max_count
                upsert_preference_keyword(slug, keyword, weight, "auto")


def get_preferences_for_category(category_slug: str) -> list[WeightedKeyword]:
    prefs = get_preference_keywords(category_slug)
    return [WeightedKeyword(p.keyword, p.weight) for p in prefs]


def score_preference_match(title: str, keywords: list[WeightedKeyword]) -> float:
    """Score 0-1 of how well a title matches the weighted keyword profile."""
    if not keywords:
        return 0.5  # Neutral if no preferences yet

    title_words = set(_extract_keywords(title))
    if not title_words:
        return 0.0

    match_score = 0.0
    max_possible = 0.0

    for kw in keywords:
        max_possible += kw.weight
        if kw.keyword in title_words:
            match_score += kw.weight

    if max_possible == 0:
        return 0.5

    return min(match_score / min(max_possible, 3), 1.0)


_last_rebuild_time = 0.0
_REBUILD_DEBOUNCE_SECONDS = 5 * 60


def trigger_preference_rebuild(category_slug: str | None = None) -> None:
    """Debounced rebuild — won't run more than once every 5 minutes."""
    global _last_rebuild_time
    now = time.monotonic()
    if now - _last_rebuild_time < _REBUILD_DEBOUNCE_SECONDS:
        return
    _last_rebuild_time = now
    rebuild_preferences(category_slug)
