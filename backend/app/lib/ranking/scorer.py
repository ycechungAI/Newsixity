"""Article scoring — faithful port of src/lib/ranking/scorer.ts.

Scores an article 0-100 from five signals (group size, preference match,
source weight, recency, title importance), then persists the batch. Uses the
same repository primitives as the Node version; the per-id ``get_article_by_id``
loop mirrors queries.ts (the N+1 there is tracked separately in Improvements.md).
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from app.db.repository import (
    DEFAULT_SCORE_WEIGHTS,
    get_article_by_id,
    get_article_group_size,
    get_feed_source_weight,
    update_article_scores,
)
from app.db.repository.helpers import Article
from app.lib.ranking.preferences import (
    WeightedKeyword,
    get_preferences_for_category,
    score_preference_match,
)

# Title importance patterns — signals that an article is high-importance news.
IMPORTANCE_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"\bbreaking\b", re.IGNORECASE), 1.0),
    (re.compile(r"\bexclusive\b", re.IGNORECASE), 0.7),
    (re.compile(r"\bjust in\b", re.IGNORECASE), 0.8),
    (re.compile(r"\bdeveloping\b", re.IGNORECASE), 0.6),
    (re.compile(r"\burgent\b", re.IGNORECASE), 0.8),
    (re.compile(r"\bcrisis\b", re.IGNORECASE), 0.5),
    (re.compile(r"\bdead\b|\bkilled\b|\bdeath toll\b", re.IGNORECASE), 0.4),
    (re.compile(r"\belection\b|\bvote\b", re.IGNORECASE), 0.3),
    (re.compile(r"\bwar\b|\binvasion\b|\battack\b", re.IGNORECASE), 0.4),
    (re.compile(r"\brecord\b|\bhistoric\b|\bunprecedented\b", re.IGNORECASE), 0.3),
    (re.compile(r"\bcrash\b|\bplunge\b|\bsurge\b|\bsoar\b", re.IGNORECASE), 0.3),
    (re.compile(r"\bannounce\b|\blaunch\b|\breveal\b", re.IGNORECASE), 0.2),
]


def _compute_title_importance(title: str) -> float:
    """Title importance score (0..1) from keyword signals."""
    score = 0.0
    for pattern, bonus in IMPORTANCE_PATTERNS:
        if pattern.search(title):
            score += bonus
    return min(score, 1.0)


def _parse_published(published_at: str) -> float | None:
    """Parse an ISO timestamp to epoch seconds, or None if unparseable.

    Mirrors JS ``new Date(x).getTime()`` returning NaN for bad input, which the
    recency scorer then treats as age-out-of-range (score 0).
    """
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _compute_recency_score(published_at: str | None) -> float:
    """Recency score (0..1). Full within 6h, linear decay to 0 by 24h."""
    if not published_at:
        return 0.3  # Unknown date gets a moderate score.

    published_time = _parse_published(published_at)
    if published_time is None:
        return 0.0  # Invalid date (matches JS NaN falling through all branches).

    now = datetime.now(timezone.utc).timestamp()
    age_hours = (now - published_time) / (60 * 60)

    if age_hours < 0:
        return 1.0  # Future date (timezone quirks).
    if age_hours <= 6:
        return 1.0
    if age_hours <= 24:
        return 1.0 - (age_hours - 6) / 18  # Linear decay 6h-24h.
    return 0.0


def score_article_parts(
    article: Article,
    preference_keywords: list[WeightedKeyword],
    weights: dict[str, int] | None = None,
) -> dict[str, float]:
    """The five score components for one article, as points.

    Split out from `score_article` so the caller can persist the breakdown
    (spec-v0.5 6.1) rather than only the total — a score nobody can
    interrogate gets ignored, and "why is this first?" has to be answerable.

    ``weights`` are the percentages each signal may contribute, keyed as in
    SCORE_WEIGHT_KEYS, and must sum to 100. None means v0.4's literals.
    """
    w = {**DEFAULT_SCORE_WEIGHTS, **(weights or {})}

    group_size = get_article_group_size(article.id)
    source_weight = get_feed_source_weight(article.feed_id)

    # Group score: 1 source = 0, 2 = 0.2, 3 = 0.4, 5+ = 1.0.
    group_score = min((group_size - 1) / 4, 1.0) * w["groupSize"]

    # Preference score.
    pref_score = score_preference_match(article.title, preference_keywords) * w["preferenceMatch"]

    # Source weight score: 0.5 = 0, 1.0 = 0.5, 2.0 = 1.0 (piecewise linear
    # around the neutral 1.0 weight).
    #
    # spec-v0.5 3.1: this clamp used to disagree with the range the API
    # accepted (0.1-10.0), so a stored 4.0 scored identically to 2.0. The API
    # now only accepts 0.5-2.0, which is exactly what this reads.
    clamped_weight = min(max(source_weight, 0.5), 2.0)
    if clamped_weight <= 1.0:
        source_weight_fraction = (clamped_weight - 0.5) / 0.5 * 0.5
    else:
        source_weight_fraction = 0.5 + (clamped_weight - 1.0) / 1.0 * 0.5
    source_score = source_weight_fraction * w["sourceWeight"]

    # Recency score.
    recency_score = _compute_recency_score(article.published_at) * w["recency"]

    # Title importance score.
    importance_score = _compute_title_importance(article.title) * w["titleImportance"]

    return {
        "groupSize": group_score,
        "preferenceMatch": pref_score,
        "sourceWeight": source_score,
        "recency": recency_score,
        "titleImportance": importance_score,
    }


def score_article(
    article: Article,
    preference_keywords: list[WeightedKeyword],
    weights: dict[str, int] | None = None,
) -> float:
    """Score a single article on a 0-100 scale.

    Weighting: group size 30%, preference match 30%, source weight 20%,
    recency 10%, title importance 10% — overridable per section via
    spec-v0.5 5.4, and identical to the above when they aren't.
    """
    parts = score_article_parts(article, preference_keywords, weights)
    total = sum(parts.values())
    # Round to 1 decimal, matching JS Math.round(x * 10) / 10 (half-up on
    # non-negative values).
    return math.floor(total * 10 + 0.5) / 10


def score_articles_for_category(
    category_slug: str,
    article_ids: list[int],
    weights: dict[str, int] | None = None,
) -> None:
    """Score a batch of articles for a category, persisting scores and parts."""
    if not article_ids:
        return

    keywords = get_preferences_for_category(category_slug)

    updates: list[dict] = []
    for article_id in article_ids:
        article = get_article_by_id(article_id)
        if not article:
            continue
        parts = score_article_parts(article, keywords, weights)
        total = sum(parts.values())
        updates.append({
            "id": article_id,
            # Same half-up rounding score_article applies, so the stored total
            # is always the sum of the stored parts.
            "score": math.floor(total * 10 + 0.5) / 10,
            "parts": parts,
        })

    if updates:
        update_article_scores(updates)
