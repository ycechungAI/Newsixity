"""Shared helpers, types, and constants for the repository layer."""

from dataclasses import dataclass

from app.db.models import Article as ArticleModel
from app.lib.utils.url import parse_http_url


@dataclass
class Article:
    """Article domain object matching the TypeScript Article type."""
    id: int
    feed_id: int
    feed_name: str
    category_slug: str
    guid: str
    title: str
    link: str
    author: str | None
    published_at: str | None
    content: str | None
    image_url: str | None
    summary: str | None
    summary_model: str | None
    is_read: bool
    is_saved: bool
    group_id: int | None
    fetched_at: str
    relevance_score: float
    is_promoted: bool


@dataclass
class Category:
    """Category domain object."""
    id: int
    name: str
    slug: str
    sort_order: int


@dataclass
class Feed:
    """Feed domain object."""
    id: int
    category_id: int
    category_slug: str | None
    name: str
    url: str
    enabled: bool
    last_fetched_at: str | None
    last_error: str | None
    source_weight: float


@dataclass
class ArticleGroup:
    """Article group domain object."""
    id: int
    label: str | None
    category_id: int
    representative_id: int | None
    article_count: int
    representative: Article
    articles: list[Article]


def map_article_row(row: dict) -> Article:
    """Map a DB row (from ARTICLE_SELECT JOIN) to an Article domain object."""
    raw_link = (row.get("link") or "").strip() if isinstance(row.get("link"), str) else ""

    # Matches TS: parseHttpUrl(row.image_url)?.toString() ?? null
    image_url = parse_http_url(row.get("image_url"))

    return Article(
        id=row["id"],
        feed_id=row["feed_id"],
        feed_name=row.get("feed_name", "") or "",
        category_slug=row.get("category_slug", "") or "",
        guid=row["guid"],
        title=row["title"],
        link=raw_link,
        author=row.get("author"),
        published_at=row.get("published_at"),
        content=row.get("content"),
        image_url=image_url,
        summary=row.get("summary"),
        summary_model=row.get("summary_model"),
        is_read=bool(row.get("is_read")),
        is_saved=bool(row.get("is_saved")),
        group_id=row.get("group_id"),
        fetched_at=row.get("fetched_at") or "",
        relevance_score=row.get("relevance_score") or 0.0,
        is_promoted=bool(row.get("is_promoted")),
    )


ARTICLE_SELECT = """
  SELECT a.*, f.name AS feed_name, c.slug AS category_slug
  FROM articles a
  JOIN feeds f ON a.feed_id = f.id
  JOIN categories c ON f.category_id = c.id
"""

# Category priority for AI summarization (Stage 4)
SUMMARIZE_CATEGORY_PRIORITY = [
    "top-news",
    "technology",
    "finance",
    "world-news",
    "gaming",
    "sports",
]

# Sports title filter patterns
SPORTS_KEYWORDS = (
    "%basketball%", "%Basketball%",
    "%NBA%", "%NCAA%",
    "%olympic%", "%Olympic%", "%Olympics%"
)
