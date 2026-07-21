"""Title deduplication via bigram similarity — port of src/lib/dedup/similarity.ts."""

import re

NEWS_PREFIXES = re.compile(
    r"^\s*(BREAKING|UPDATE|UPDATED|EXCLUSIVE|OPINION|ANALYSIS|WATCH|LIVE|"
    r"DEVELOPING|JUST IN|BREAKING NEWS|REPORT|VIDEO|PHOTOS?|GALLERY|INTERVIEW|"
    r"REVIEW|EXPLAINER|FACT CHECK|COLUMN|EDITORIAL|LETTER|COMMENTARY)\s*:\s*",
    re.IGNORECASE,
)


def normalize_title_for_hash(title: str) -> str:
    """Normalize a title by removing prefixes, special chars, and normalizing whitespace."""
    normalized = title.lower()
    normalized = NEWS_PREFIXES.sub("", normalized)
    normalized = re.sub(r"[^\w\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def hash_title(title: str) -> str:
    """Hash a title (same as normalize for this implementation)."""
    return normalize_title_for_hash(title)


def get_bigrams(text: str) -> list[str]:
    """Extract all 2-character bigrams from a string."""
    bigrams = []
    for i in range(len(text) - 1):
        bigrams.append(text[i:i + 2])
    return bigrams


def bigram_similarity(a: str, b: str) -> float:
    """Calculate similarity between two strings using Dice coefficient on bigrams."""
    normalized_a = normalize_title_for_hash(a)
    normalized_b = normalize_title_for_hash(b)

    if normalized_a == normalized_b:
        return 1.0
    if len(normalized_a) < 2 or len(normalized_b) < 2:
        return 0.0

    bigrams_a = get_bigrams(normalized_a)
    bigrams_b = get_bigrams(normalized_b)

    if not bigrams_a or not bigrams_b:
        return 0.0

    # Count bigrams in B
    bigram_counts_b = {}
    for bigram in bigrams_b:
        bigram_counts_b[bigram] = bigram_counts_b.get(bigram, 0) + 1

    # Count intersection with B
    intersection_size = 0
    used_b = {}

    for bigram in bigrams_a:
        available_in_b = bigram_counts_b.get(bigram, 0) - used_b.get(bigram, 0)
        if available_in_b > 0:
            intersection_size += 1
            used_b[bigram] = used_b.get(bigram, 0) + 1

    # Dice coefficient: 2 * |intersection| / (|A| + |B|)
    return (2 * intersection_size) / (len(bigrams_a) + len(bigrams_b))


def is_duplicate(new_title: str, existing_title: str, threshold: float = 0.7) -> bool:
    """Check if two titles are duplicates based on bigram similarity threshold."""
    return bigram_similarity(new_title, existing_title) >= threshold
