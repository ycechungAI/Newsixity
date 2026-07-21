"""SQLAlchemy models — faithful port of src/lib/db/schema.ts.

Parity notes (intentional, to match the existing 109 MB database exactly):
  * Timestamps are stored as TEXT via ``datetime('now')`` server defaults, so
    they map to ``str`` here (better-sqlite3 returned TEXT, not datetimes).
  * Boolean-ish columns (is_read, is_saved, enabled, is_promoted) stay INTEGER
    0/1 rather than Boolean, matching the on-disk representation.
  * The three columns the Node app added via runtime ALTERs
    (articles.relevance_score, articles.is_promoted, feeds.source_weight) are
    declared directly here; create_all leaves the existing table untouched.
  * No new indexes beyond schema.ts — the (is_read, published_at) compound index
    is tracked as a separate improvement, not part of this faithful port.
  * Every table sets ``sqlite_autoincrement=True`` (SONNET FIX — Stage 1a
    originally omitted this): schema.ts declares ``INTEGER PRIMARY KEY
    AUTOINCREMENT`` on every table, which stops SQLite from reusing a
    deleted row's rowid. SQLAlchemy's per-column ``autoincrement=True`` is
    a logical flag only and does NOT emit that SQL keyword for SQLite —
    without this table option, article/group/setting ids could be recycled
    after a delete on any freshly created (non-production) database,
    silently pointing stale foreign keys or bookmarked /article/{id} links
    at a different row.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, Float, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_NOW = text("(datetime('now'))")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)

    __table_args__ = {"sqlite_autoincrement": True}


class Feed(Base):
    __tablename__ = "feeds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("categories.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    last_fetched_at: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)
    # Added via migration in schema.ts.
    source_weight: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=text("1.0")
    )

    __table_args__ = (
        Index("idx_feeds_category_id", "category_id"),
        {"sqlite_autoincrement": True},
    )


class ArticleGroup(Base):
    __tablename__ = "article_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("categories.id"), nullable=False
    )
    # No FK in schema.ts — representative_id is a bare INTEGER there.
    representative_id: Mapped[int | None] = mapped_column(Integer)
    article_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)

    __table_args__ = (
        Index("idx_article_groups_category_id", "category_id"),
        {"sqlite_autoincrement": True},
    )


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feed_id: Mapped[int] = mapped_column(Integer, ForeignKey("feeds.id"), nullable=False)
    guid: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    summary_model: Mapped[str | None] = mapped_column(Text)
    is_read: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_saved: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    group_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("article_groups.id"))
    title_hash: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)
    # Added via migration in schema.ts.
    relevance_score: Mapped[float | None] = mapped_column(Float, server_default=text("0"))
    is_promoted: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    __table_args__ = (
        UniqueConstraint("feed_id", "guid", name="uq_articles_feed_guid"),
        Index("idx_articles_feed_id", "feed_id"),
        Index("idx_articles_group_id", "group_id"),
        Index("idx_articles_published_at", text("published_at DESC")),
        Index("idx_articles_title_hash", "title_hash"),
        Index("idx_articles_is_saved", "is_saved", sqlite_where=text("is_saved = 1")),
        Index("idx_articles_promoted", "is_promoted", sqlite_where=text("is_promoted = 1")),
        Index("idx_articles_relevance", text("relevance_score DESC")),
        {"sqlite_autoincrement": True},
    )


class ArticleResearch(Base):
    __tablename__ = "article_research"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(Integer, ForeignKey("articles.id"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'[]'"))
    model: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)

    __table_args__ = (
        Index("idx_article_research_article_id", "article_id"),
        {"sqlite_autoincrement": True},
    )


class SearchQuota(Base):
    __tablename__ = "search_quota"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    month_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    query_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)

    __table_args__ = {"sqlite_autoincrement": True}


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    value: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)

    __table_args__ = {"sqlite_autoincrement": True}


class StockWatchlist(Base):
    __tablename__ = "stock_watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    exchange: Mapped[str | None] = mapped_column(Text)
    added_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)

    __table_args__ = {"sqlite_autoincrement": True}


class StockQuoteCache(Base):
    __tablename__ = "stock_quotes_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    change: Mapped[float] = mapped_column(Float, nullable=False)
    change_percent: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int | None] = mapped_column(Integer)
    market_cap: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(Text)
    cached_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)
    expires_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("idx_stock_quotes_expires", "expires_at"),
        {"sqlite_autoincrement": True},
    )


class StockChartCache(Base):
    __tablename__ = "stock_charts_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    timeframe: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[str] = mapped_column(Text, nullable=False)
    cached_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)
    expires_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", name="uq_stock_charts_symbol_timeframe"),
        Index("idx_stock_charts_expires", "expires_at"),
        {"sqlite_autoincrement": True},
    )


class MarketHeatmapSnapshot(Base):
    __tablename__ = "market_heatmap_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    data: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)

    __table_args__ = (
        Index("idx_heatmap_snapshots_date", text("date DESC")),
        {"sqlite_autoincrement": True},
    )


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_slug: Mapped[str] = mapped_column(Text, nullable=False)
    keyword: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("1.0"))
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'auto'"))
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)

    __table_args__ = (
        UniqueConstraint("category_slug", "keyword", name="uq_user_preferences_category_keyword"),
        Index("idx_user_preferences_category", "category_slug"),
        {"sqlite_autoincrement": True},
    )
