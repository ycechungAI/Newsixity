"""Finance queries — port of queries.ts:1140-1365.

Covers watchlist, quote/chart TTL caching, and market heatmap snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db.models import MarketHeatmapSnapshot as HeatmapModel
from app.db.models import StockChartCache as ChartCacheModel
from app.db.models import StockQuoteCache as QuoteCacheModel
from app.db.models import StockWatchlist as WatchlistModel
from app.db.session import SessionLocal


def _js_iso_string(dt: datetime) -> str:
    """Match JS Date.toISOString(): milliseconds precision, literal 'Z' suffix.

    (Not Python's default isoformat(), which emits microseconds and '+00:00' —
    SQLite's datetime() parses both, but this keeps new rows byte-identical
    to what the Node app would have written.)
    """
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


@dataclass
class WatchlistItem:
    id: int
    symbol: str
    name: str
    exchange: str | None
    added_at: str


@dataclass
class StockQuote:
    """Matches queries.ts getCachedQuote's return shape (partial StockQuote)."""
    symbol: str
    name: str
    exchange: str
    price: float
    change: float
    change_percent: float
    volume: int | None
    market_cap: float | None
    currency: str
    fifty_two_week_high: float | None
    fifty_two_week_low: float | None
    market_state: str


@dataclass
class ChartDataPoint:
    date: str
    price: float
    volume: int | None = None


@dataclass
class HeatmapSnapshot:
    id: int
    date: str
    data: str
    created_at: str


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

def get_watchlist() -> list[WatchlistItem]:
    with SessionLocal() as db:
        rows = db.execute(
            select(WatchlistModel).order_by(WatchlistModel.added_at.desc())
        ).scalars().all()
        return [
            WatchlistItem(
                id=r.id, symbol=r.symbol, name=r.name,
                exchange=r.exchange, added_at=r.added_at,
            )
            for r in rows
        ]


def add_to_watchlist(symbol: str, name: str, exchange: str) -> int:
    with SessionLocal() as db:
        item = WatchlistModel(symbol=symbol, name=name, exchange=exchange)
        db.add(item)
        db.commit()
        db.refresh(item)
        return item.id


def remove_from_watchlist(item_id: int) -> None:
    with SessionLocal() as db:
        row = db.execute(
            select(WatchlistModel).where(WatchlistModel.id == item_id)
        ).scalar_one_or_none()
        if row:
            db.delete(row)
            db.commit()


def is_in_watchlist(symbol: str) -> bool:
    with SessionLocal() as db:
        row = db.execute(
            select(WatchlistModel.id).where(WatchlistModel.symbol == symbol)
        ).scalar_one_or_none()
        return row is not None


# ---------------------------------------------------------------------------
# Quote Cache
# ---------------------------------------------------------------------------

def _row_to_quote(row: QuoteCacheModel) -> StockQuote:
    return StockQuote(
        symbol=row.symbol,
        name="",  # Not stored in cache; filled from watchlist by caller.
        exchange="",
        price=row.price,
        change=row.change,
        change_percent=row.change_percent,
        volume=row.volume,
        market_cap=row.market_cap,
        currency=row.currency or "USD",
        fifty_two_week_high=None,
        fifty_two_week_low=None,
        market_state="CLOSED",
    )


def get_cached_quote(symbol: str) -> StockQuote | None:
    with SessionLocal() as db:
        row = db.execute(
            select(QuoteCacheModel).where(
                QuoteCacheModel.symbol == symbol,
                func.datetime(QuoteCacheModel.expires_at) > func.datetime("now"),
            )
        ).scalar_one_or_none()
        return _row_to_quote(row) if row else None


def set_cached_quote(quote: StockQuote, ttl_minutes: int) -> None:
    expires_at = _js_iso_string(datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes))

    with SessionLocal() as db:
        stmt = sqlite_insert(QuoteCacheModel).values(
            symbol=quote.symbol,
            price=quote.price,
            change=quote.change,
            change_percent=quote.change_percent,
            volume=quote.volume,
            market_cap=quote.market_cap,
            currency=quote.currency,
            expires_at=expires_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol"],
            set_={
                "price": stmt.excluded.price,
                "change": stmt.excluded.change,
                "change_percent": stmt.excluded.change_percent,
                "volume": stmt.excluded.volume,
                "market_cap": stmt.excluded.market_cap,
                "currency": stmt.excluded.currency,
                "cached_at": func.datetime("now"),
                "expires_at": stmt.excluded.expires_at,
            },
        )
        db.execute(stmt)
        db.commit()


def get_cached_quotes(symbols: list[str]) -> dict[str, StockQuote]:
    """Batch version — single IN(...) query instead of N round trips."""
    if not symbols:
        return {}

    with SessionLocal() as db:
        rows = db.execute(
            select(QuoteCacheModel).where(
                QuoteCacheModel.symbol.in_(symbols),
                func.datetime(QuoteCacheModel.expires_at) > func.datetime("now"),
            )
        ).scalars().all()

        return {row.symbol: _row_to_quote(row) for row in rows}


# ---------------------------------------------------------------------------
# Chart Cache
# ---------------------------------------------------------------------------

def get_cached_chart(symbol: str, timeframe: str) -> dict | None:
    """Returns {"data": [...], "cached": True} or None."""
    import json

    with SessionLocal() as db:
        row = db.execute(
            select(ChartCacheModel.data).where(
                ChartCacheModel.symbol == symbol,
                ChartCacheModel.timeframe == timeframe,
                func.datetime(ChartCacheModel.expires_at) > func.datetime("now"),
            )
        ).scalar_one_or_none()

    if not row:
        return None

    try:
        data = json.loads(row)
        return {"data": data, "cached": True}
    except (ValueError, TypeError):
        return None


def set_cached_chart(
    symbol: str, timeframe: str, data: list[dict], ttl_hours: int
) -> None:
    import json

    expires_at = _js_iso_string(datetime.now(timezone.utc) + timedelta(hours=ttl_hours))
    data_json = json.dumps(data)

    with SessionLocal() as db:
        stmt = sqlite_insert(ChartCacheModel).values(
            symbol=symbol, timeframe=timeframe, data=data_json, expires_at=expires_at
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "timeframe"],
            set_={
                "data": stmt.excluded.data,
                "cached_at": func.datetime("now"),
                "expires_at": stmt.excluded.expires_at,
            },
        )
        db.execute(stmt)
        db.commit()


# ---------------------------------------------------------------------------
# Cache Cleanup
# ---------------------------------------------------------------------------

def clean_expired_quotes() -> int:
    with SessionLocal() as db:
        rows = db.execute(
            select(QuoteCacheModel).where(func.datetime(QuoteCacheModel.expires_at) <= func.datetime("now"))
        ).scalars().all()
        count = len(rows)
        for r in rows:
            db.delete(r)
        db.commit()
        return count


def clean_expired_charts() -> int:
    with SessionLocal() as db:
        rows = db.execute(
            select(ChartCacheModel).where(func.datetime(ChartCacheModel.expires_at) <= func.datetime("now"))
        ).scalars().all()
        count = len(rows)
        for r in rows:
            db.delete(r)
        db.commit()
        return count


# ---------------------------------------------------------------------------
# Market Heatmap Snapshots
# ---------------------------------------------------------------------------

def get_heatmap_snapshot(date: str) -> HeatmapSnapshot | None:
    with SessionLocal() as db:
        row = db.execute(
            select(HeatmapModel).where(HeatmapModel.date == date)
        ).scalar_one_or_none()
        if not row:
            return None
        return HeatmapSnapshot(id=row.id, date=row.date, data=row.data, created_at=row.created_at)


def save_heatmap_snapshot(date: str, data: str) -> int:
    with SessionLocal() as db:
        stmt = sqlite_insert(HeatmapModel).values(date=date, data=data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["date"],
            set_={"data": stmt.excluded.data, "created_at": func.datetime("now")},
        )
        result = db.execute(stmt)
        db.commit()

        row = db.execute(
            select(HeatmapModel.id).where(HeatmapModel.date == date)
        ).scalar_one()
        return row


def get_available_heatmap_dates() -> list[str]:
    with SessionLocal() as db:
        rows = db.execute(
            select(HeatmapModel.date).order_by(HeatmapModel.date.desc()).limit(30)
        ).scalars().all()
        return list(rows)


def delete_old_heatmap_snapshots(keep_days: int = 30) -> int:
    with SessionLocal() as db:
        rows = db.execute(
            select(HeatmapModel).where(
                HeatmapModel.date < func.date("now", f"-{keep_days} days")
            )
        ).scalars().all()
        count = len(rows)
        for r in rows:
            db.delete(r)
        db.commit()
        return count
