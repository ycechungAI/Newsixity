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
        Index("idx_articles_is_read_published", "is_read", text("published_at DESC")),
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


class DailyBriefing(Base):
    """One AI briefing per local date (v0.4 §3). The unique date is what makes
    "generate once, serve many times" safe — same shape as the heatmap
    snapshots above. ``sources`` is a JSON list of {n, articleId, title} so
    the [n] citations in ``content`` can link back to articles."""

    __tablename__ = "daily_briefing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'[]'"))
    model: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)

    __table_args__ = (
        Index("idx_daily_briefing_date", text("date DESC")),
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


class PodcastFeed(Base):
    __tablename__ = "podcast_feeds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    feed_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    site_url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    is_favorite: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_fetched_at: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)

    __table_args__ = {"sqlite_autoincrement": True}


class PodcastEpisode(Base):
    __tablename__ = "podcast_episodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    podcast_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("podcast_feeds.id"), nullable=False
    )
    guid: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    audio_url: Mapped[str] = mapped_column(Text, nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    published_at: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    is_favorite: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    progress_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_played: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)

    __table_args__ = (
        UniqueConstraint("podcast_id", "guid", name="uq_podcast_episodes_podcast_guid"),
        Index("idx_podcast_episodes_podcast_id", "podcast_id"),
        Index("idx_podcast_episodes_published_at", text("published_at DESC")),
        {"sqlite_autoincrement": True},
    )


class WeatherLocation(Base):
    """Persisted user cities. Gives WeatherObservation/WeatherDaily a stable

    key instead of the frontend's fragile float-formatted "lat,lon" string.
    """

    __tablename__ = "weather_locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # The place the weather page opens on, and the one the hero card shows.
    # Added post-hoc; init_db ALTERs it onto existing databases.
    is_active: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)

    __table_args__ = (
        UniqueConstraint("latitude", "longitude", name="uq_weather_locations_lat_lon"),
        {"sqlite_autoincrement": True},
    )


class YoutubePlaylistCache(Base):
    """Scrape cache for YouTube playlists, keyed by playlist id.

    Was an in-process dict, which meant every app restart began cold. A cold
    cache is what made the "Video unavailable" flash visible: a playlist-only
    URL mounts ``/embed/videoseries?list=...`` — a form with no video in it —
    until the playlist resolves and the frontend swaps in a real video id, so
    the longer the fetch takes, the longer the broken frame is on screen.

    A *new* table, so ``create_all`` builds it on an existing database with no
    ALTER and no migration — create_all only fails to change a table that
    already exists.

    ``payload`` is the full JSON response the API returns (items, totalItems,
    source). ``source`` is duplicated as a column so a degraded RSS scrape is
    visible without parsing the JSON back out.
    """

    __tablename__ = "youtube_playlist_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    playlist_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'scrape'"))
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # ISO-8601 UTC, same format as the rest of the schema.
    expires_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)

    __table_args__ = (
        Index("idx_youtube_playlist_cache_expires", "expires_at"),
        {"sqlite_autoincrement": True},
    )


class WeatherObservation(Base):
    """Point-in-time current-conditions snapshot for a location."""

    __tablename__ = "weather_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("weather_locations.id"), nullable=False
    )
    observed_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)
    temperature: Mapped[float | None] = mapped_column(Float)
    apparent_temperature: Mapped[float | None] = mapped_column(Float)
    humidity: Mapped[float | None] = mapped_column(Float)
    wind_speed: Mapped[float | None] = mapped_column(Float)
    weather_code: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        Index(
            "idx_weather_observations_location_observed",
            "location_id",
            text("observed_at DESC"),
        ),
        {"sqlite_autoincrement": True},
    )


class WeatherDaily(Base):
    """One row per (location, date). Open-Meteo's ``daily`` response is

    columnar parallel arrays; callers pivot to rows before upserting here.
    """

    __tablename__ = "weather_daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("weather_locations.id"), nullable=False
    )
    date: Mapped[str] = mapped_column(Text, nullable=False)
    temp_max: Mapped[float | None] = mapped_column(Float)
    temp_min: Mapped[float | None] = mapped_column(Float)
    precipitation_sum: Mapped[float | None] = mapped_column(Float)
    weather_code: Mapped[int | None] = mapped_column(Integer)
    wind_speed_max: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=_NOW)

    __table_args__ = (
        UniqueConstraint("location_id", "date", name="uq_weather_daily_location_date"),
        Index("idx_weather_daily_location_date", "location_id", text("date DESC")),
        {"sqlite_autoincrement": True},
    )
