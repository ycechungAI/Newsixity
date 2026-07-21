"""Yahoo Finance integration via yfinance — port of src/lib/finance/yahoo.ts.

yfinance's Ticker/Search calls are synchronous (blocking network I/O), so every
public function here runs the actual call in a worker thread via
asyncio.to_thread to avoid blocking the event loop, matching the async
signatures the Node app's yahoo-finance2-based module exposed.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import yfinance as yf

from app.db.repository.finance import StockQuote

# yfinance's `history(period=...)` accepts these values directly.
_VALID_PERIODS = {"1d", "5d", "1mo", "3mo", "1y"}
_INTERVAL_BY_TIMEFRAME = {"1d": "5m", "5d": "1h", "1mo": "1d", "3mo": "1d", "1y": "1d"}


class StockNotFoundError(Exception):
    pass


def _quote_sync(symbol: str) -> StockQuote:
    info = yf.Ticker(symbol).info or {}

    if not info.get("regularMarketPrice") and not info.get("symbol"):
        raise StockNotFoundError(f"Stock {symbol} not found (possibly delisted)")

    return StockQuote(
        symbol=info.get("symbol") or symbol,
        name=info.get("longName") or info.get("shortName") or symbol,
        exchange=info.get("fullExchangeName") or info.get("exchange") or "UNKNOWN",
        price=info.get("regularMarketPrice") or 0,
        change=info.get("regularMarketChange") or 0,
        change_percent=info.get("regularMarketChangePercent") or 0,
        volume=info.get("regularMarketVolume"),
        market_cap=info.get("marketCap"),
        currency=info.get("currency") or "USD",
        fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
        fifty_two_week_low=info.get("fiftyTwoWeekLow"),
        market_state=info.get("marketState") or "CLOSED",
    )


async def fetch_quote(symbol: str) -> StockQuote:
    return await asyncio.to_thread(_quote_sync, symbol)


async def fetch_quotes(symbols: list[str]) -> dict[str, StockQuote]:
    """Batch fetch; individual failures are dropped, matching Promise.allSettled."""
    results = await asyncio.gather(
        *(fetch_quote(s) for s in symbols), return_exceptions=True
    )
    quotes: dict[str, StockQuote] = {}
    for symbol, result in zip(symbols, results):
        if isinstance(result, Exception):
            continue
        quotes[symbol] = result
    return quotes


def _chart_sync(symbol: str, timeframe: str) -> list[dict]:
    period = timeframe if timeframe in _VALID_PERIODS else "1mo"
    interval = _INTERVAL_BY_TIMEFRAME.get(period, "1d")

    history = yf.Ticker(symbol).history(period=period, interval=interval)
    if history is None or history.empty:
        return []

    points: list[dict] = []
    for index, row in history.iterrows():
        date = index.to_pydatetime() if hasattr(index, "to_pydatetime") else index
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        close = row.get("Close")
        volume = row.get("Volume")
        points.append(
            {
                "date": date.isoformat(),
                "price": float(close) if close is not None and close == close else 0.0,
                "volume": int(volume) if volume is not None and volume == volume else None,
            }
        )
    return points


async def fetch_chart(symbol: str, timeframe: str) -> list[dict]:
    try:
        return await asyncio.to_thread(_chart_sync, symbol, timeframe)
    except Exception:
        return []


def _search_sync(query: str) -> list[dict]:
    from yfinance import Search

    quotes = Search(query, max_results=10).quotes or []
    results: list[dict] = []
    for q in quotes:
        symbol = q.get("symbol")
        shortname = q.get("shortname")
        if not symbol or not shortname:
            continue
        results.append(
            {
                "symbol": symbol,
                "name": shortname or q.get("longname") or symbol,
                "exchange": q.get("exchDisp") or q.get("exchange") or "UNKNOWN",
                "type": q.get("quoteType") or "EQUITY",
            }
        )
    return results[:10]


async def search_stocks(query: str) -> list[dict]:
    try:
        return await asyncio.to_thread(_search_sync, query)
    except Exception:
        return []
