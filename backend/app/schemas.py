"""Pydantic schemas for API request/response validation.

Port of src/types/index.ts and inline zod validators from all API routes.
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Category(BaseModel):
    id: int
    name: str
    slug: str
    sortOrder: int = Field(validation_alias="sort_order", default=0)

    model_config = {"populate_by_name": True}


class CategoryWithCounts(Category):
    total: int = 0
    unread: int = 0


class Feed(BaseModel):
    id: int
    categoryId: int = Field(validation_alias="category_id")
    categorySlug: Optional[str] = Field(validation_alias="category_slug", default=None)
    name: str
    url: str
    enabled: bool
    lastFetchedAt: Optional[str] = Field(validation_alias="last_fetched_at", default=None)
    lastError: Optional[str] = Field(validation_alias="last_error", default=None)
    sourceWeight: float = Field(validation_alias="source_weight", default=1.0)

    model_config = {"populate_by_name": True}


class Article(BaseModel):
    id: int
    feedId: int = Field(validation_alias="feed_id")
    feedName: str = Field(validation_alias="feed_name")
    categorySlug: str = Field(validation_alias="category_slug")
    guid: str
    title: str
    link: str
    author: Optional[str] = None
    publishedAt: Optional[str] = Field(validation_alias="published_at", default=None)
    content: Optional[str] = None
    imageUrl: Optional[str] = Field(validation_alias="image_url", default=None)
    summary: Optional[str] = None
    summaryModel: Optional[str] = Field(validation_alias="summary_model", default=None)
    isRead: bool = Field(validation_alias="is_read")
    isSaved: bool = Field(validation_alias="is_saved")
    groupId: Optional[int] = Field(validation_alias="group_id", default=None)
    fetchedAt: str = Field(validation_alias="fetched_at")
    relevanceScore: float = Field(validation_alias="relevance_score", default=0.0)
    isPromoted: bool = Field(validation_alias="is_promoted", default=False)
    highlight: Optional[str] = None

    model_config = {"populate_by_name": True}


class ArticleGroup(BaseModel):
    id: int
    label: Optional[str] = None
    categoryId: int = Field(validation_alias="category_id")
    representativeId: int = Field(validation_alias="representative_id")
    articleCount: int = Field(validation_alias="article_count")
    representative: Article
    articles: list[Article]

    model_config = {"populate_by_name": True}


class ResearchSource(BaseModel):
    url: str
    title: str
    snippet: str


class ArticleResearch(BaseModel):
    id: int
    articleId: int = Field(validation_alias="article_id")
    question: str
    answer: str
    sources: list[ResearchSource]
    model: Optional[str] = None
    createdAt: str = Field(validation_alias="created_at")

    model_config = {"populate_by_name": True}


class UserPreference(BaseModel):
    id: int
    categorySlug: str = Field(validation_alias="category_slug")
    keyword: str
    weight: float
    source: str  # "auto" or "manual"
    updatedAt: str = Field(validation_alias="updated_at")

    model_config = {"populate_by_name": True}


class StockQuote(BaseModel):
    symbol: str
    price: float
    change: float
    changePercent: float = Field(validation_alias="change_percent")
    volume: Optional[int] = None
    marketCap: Optional[float] = Field(validation_alias="market_cap", default=None)
    currency: Optional[str] = None
    cachedAt: str = Field(validation_alias="cached_at")
    expiresAt: str = Field(validation_alias="expires_at")

    model_config = {"populate_by_name": True}


class StockChartData(BaseModel):
    symbol: str
    timeframe: str
    data: str  # JSON string of the chart data
    cachedAt: str = Field(validation_alias="cached_at")
    expiresAt: str = Field(validation_alias="expires_at")

    model_config = {"populate_by_name": True}


class MarketHeatmapSnapshot(BaseModel):
    date: str
    data: str  # JSON string of the heatmap data
    createdAt: str = Field(validation_alias="created_at")

    model_config = {"populate_by_name": True}


class HealthStatus(BaseModel):
    db: bool
    ollama: bool
    ollamaModels: list[str] = Field(validation_alias="ollama_models")
    feedsCount: int = Field(validation_alias="feeds_count")
    articlesCount: int = Field(validation_alias="articles_count")
    lastRefresh: Optional[str] = Field(validation_alias="last_refresh", default=None)

    model_config = {"populate_by_name": True}


class RefreshResult(BaseModel):
    refreshed: int
    newArticles: int = Field(validation_alias="new_articles")
    errors: list[str]

    model_config = {"populate_by_name": True}


# Request schemas


class ResearchRequestBody(BaseModel):
    articleId: int = Field(validation_alias="article_id")
    question: str

    @field_validator("articleId")
    @classmethod
    def validate_article_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Article ID must be positive")
        return v

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed or len(trimmed) > 500:
            raise ValueError("Question must be 1-500 characters")
        return trimmed

    model_config = {"populate_by_name": True}


class AskHistoryTurn(BaseModel):
    """One prior Q&A turn, sent back by the frontend for follow-up context."""

    question: str
    answer: str


class AskRequestBody(BaseModel):
    question: str
    history: list[AskHistoryTurn] = Field(default_factory=list)

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed or len(trimmed) > 500:
            raise ValueError("Question must be 1-500 characters")
        return trimmed

    model_config = {"populate_by_name": True}


class PreferenceCreateRequestBody(BaseModel):
    categorySlug: str = Field(validation_alias="category_slug")
    keyword: str
    weight: Optional[float] = Field(default=1.0)
    source: Optional[str] = Field(default="auto")

    @field_validator("categorySlug", "keyword")
    @classmethod
    def validate_strings(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Field must not be empty")
        return trimmed

    @field_validator("keyword")
    @classmethod
    def validate_keyword_length(cls, v: str) -> str:
        if len(v) > 120:
            raise ValueError("Keyword must be <= 120 characters")
        return v

    @field_validator("weight")
    @classmethod
    def validate_weight(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v < 0.1 or v > 5.0):
            raise ValueError("Weight must be between 0.1 and 5.0")
        return v

    model_config = {"populate_by_name": True}


class PreferenceDeleteRequestQuery(BaseModel):
    id: int


class PreferenceRebuildRequestBody(BaseModel):
    categorySlug: Optional[str] = Field(validation_alias="category_slug", default=None)

    model_config = {"populate_by_name": True}


class ManualArticleRequestBody(BaseModel):
    url: str
    title: str
    content: Optional[str] = None
    imageUrl: Optional[str] = Field(validation_alias="image_url", default=None)
    author: Optional[str] = None

    @field_validator("url", "imageUrl", mode="before")
    @classmethod
    def validate_http_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must use http:// or https://")
        return v

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v or len(v) > 500:
            raise ValueError("Title must be 1-500 characters")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 50000:
            raise ValueError("Content must be <= 50000 characters")
        return v

    model_config = {"populate_by_name": True}


class ManualArticleDeleteRequestQuery(BaseModel):
    id: int


class SettingsUpdateRequestBody(BaseModel):
    brave_search_api_key: Optional[str] = None
    ollama_model: Optional[str] = None
    ollama_host: Optional[str] = None

    @field_validator("brave_search_api_key")
    @classmethod
    def validate_api_key(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 2048:
            raise ValueError("API key must be <= 2048 characters")
        return v

    @field_validator("ollama_model")
    @classmethod
    def validate_ollama_model(cls, v: Optional[str]) -> Optional[str]:
        if v:
            trimmed = v.strip()
            if not trimmed or len(trimmed) > 128:
                raise ValueError("Ollama model must be 1-128 characters")
            return trimmed
        return v

    @field_validator("ollama_host")
    @classmethod
    def validate_ollama_host(cls, v: Optional[str]) -> Optional[str]:
        if v:
            trimmed = v.strip()
            if len(trimmed) > 512:
                raise ValueError("Ollama host must be <= 512 characters")
            if not trimmed.startswith(("http://", "https://")):
                raise ValueError("Ollama host must use http:// or https://")
            return trimmed
        return v


def _clean_feed_name(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    trimmed = " ".join(v.split())
    if not trimmed or len(trimmed) > 120:
        raise ValueError("Feed name must be 1-120 characters")
    return trimmed


_SLUG_PATTERN = r"^[a-z0-9-]{1,40}$"


class FeedCreateRequestBody(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    name: Optional[str] = None
    categorySlug: str = Field(validation_alias="category_slug", pattern=_SLUG_PATTERN)

    _name = field_validator("name")(_clean_feed_name)

    model_config = {"populate_by_name": True}


class FeedUpdateRequestBody(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    categorySlug: Optional[str] = Field(
        validation_alias="category_slug", default=None, pattern=_SLUG_PATTERN
    )

    _name = field_validator("name")(_clean_feed_name)

    model_config = {"populate_by_name": True}


class FeedWeightUpdateRequestBody(BaseModel):
    feedId: int = Field(validation_alias="feed_id")
    weight: float

    @field_validator("weight")
    @classmethod
    def validate_weight(cls, v: float) -> float:
        if v < 0.1 or v > 10.0:
            raise ValueError("Weight must be between 0.1 and 10.0")
        return v

    model_config = {"populate_by_name": True}


class SearchResultsRequestBody(BaseModel):
    url: str
    results: list[dict]  # [{title, url, description}]

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must use http:// or https://")
        return v


class FinanceQuoteRequestQuery(BaseModel):
    symbols: Optional[str] = None  # Comma-separated


class FinanceChartRequestQuery(BaseModel):
    symbol: str
    timeframe: str  # "1d", "7d", "30d", etc.


class FinanceSearchRequestBody(BaseModel):
    query: str
    limit: Optional[int] = Field(default=5)


class FinanceWatchlistActionRequestBody(BaseModel):
    symbol: str
    name: str
    exchange: Optional[str] = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        import re

        trimmed = v.strip()
        if not trimmed or len(trimmed) > 15 or not re.match(r"^[A-Za-z0-9.^-]+$", trimmed):
            raise ValueError("Invalid symbol")
        return trimmed


class FinanceWatchlistDeleteRequestBody(BaseModel):
    id: int

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("id must be positive")
        return v


class ArticlesMarkAllReadRequestBody(BaseModel):
    categorySlug: Optional[str] = Field(validation_alias="category_slug", default=None)

    model_config = {"populate_by_name": True}


class ArticlesBulkMarkReadRequestBody(BaseModel):
    articleIds: list[int] = Field(validation_alias="article_ids")

    model_config = {"populate_by_name": True}


# Podcast schemas


class PodcastFeedSchema(BaseModel):
    id: int
    title: str
    feedUrl: str = Field(validation_alias="feed_url")
    siteUrl: Optional[str] = Field(validation_alias="site_url", default=None)
    description: Optional[str] = None
    imageUrl: Optional[str] = Field(validation_alias="image_url", default=None)
    author: Optional[str] = None
    isFavorite: bool = Field(validation_alias="is_favorite", default=False)
    lastFetchedAt: Optional[str] = Field(validation_alias="last_fetched_at", default=None)
    lastError: Optional[str] = Field(validation_alias="last_error", default=None)
    createdAt: str = Field(validation_alias="created_at")

    model_config = {"populate_by_name": True}


class PodcastEpisodeSchema(BaseModel):
    id: int
    podcastId: int = Field(validation_alias="podcast_id")
    guid: str
    title: str
    audioUrl: str = Field(validation_alias="audio_url")
    durationSeconds: Optional[int] = Field(validation_alias="duration_seconds", default=None)
    publishedAt: Optional[str] = Field(validation_alias="published_at", default=None)
    description: Optional[str] = None
    isFavorite: bool = Field(validation_alias="is_favorite", default=False)
    progressSeconds: int = Field(validation_alias="progress_seconds", default=0)
    isPlayed: bool = Field(validation_alias="is_played", default=False)
    createdAt: str = Field(validation_alias="created_at")

    model_config = {"populate_by_name": True}


class PodcastSubscribeSchema(BaseModel):
    feedUrl: str = Field(validation_alias="feed_url")

    model_config = {"populate_by_name": True}


# Response/utility schemas


class ErrorResponse(BaseModel):
    error: str


class SuccessResponse(BaseModel):
    success: bool


class MessageResponse(BaseModel):
    message: str


class DataResponse(BaseModel):
    data: dict
