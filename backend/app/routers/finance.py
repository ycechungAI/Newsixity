"""Finance endpoints — /api/finance/*.

Port of src/app/api/finance/{quote,chart,heatmap,search,watchlist}/route.ts.
"""

import re
from dataclasses import asdict
from datetime import date as date_cls
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.lib.server.rate_limit import TEN_MIN_MS, rate_limit
from app.db.repository import (
    add_to_watchlist,
    clean_expired_charts,
    clean_expired_quotes,
    get_available_heatmap_dates,
    get_cached_chart,
    get_cached_quote,
    get_cached_quotes,
    get_heatmap_snapshot,
    get_watchlist,
    is_in_watchlist,
    remove_from_watchlist,
    save_heatmap_snapshot,
    set_cached_chart,
    set_cached_quote,
)
from app.lib.finance.sp500 import SP500_STOCKS
from app.lib.integrations import fetch_chart, fetch_quotes, search_stocks
from app.schemas import FinanceWatchlistActionRequestBody, FinanceWatchlistDeleteRequestBody

router = APIRouter()


def _quote_to_camel(quote) -> dict:
    """dataclasses.asdict() emits the StockQuote dataclass's snake_case field
    names verbatim (change_percent, market_cap, fifty_two_week_high, ...) —
    these responses never pass through the aliased Pydantic schemas, so
    nothing translates them. The frontend's StockQuote type
    (src/lib/finance/types.ts) only reads camelCase; without this the
    watchlist/heatmap cards read undefined for every numeric field.
    """
    d = asdict(quote)
    return {
        "symbol": d["symbol"],
        "name": d["name"],
        "exchange": d["exchange"],
        "price": d["price"],
        "change": d["change"],
        "changePercent": d["change_percent"],
        "volume": d["volume"],
        "marketCap": d["market_cap"],
        "currency": d["currency"],
        "fiftyTwoWeekHigh": d["fifty_two_week_high"],
        "fiftyTwoWeekLow": d["fifty_two_week_low"],
        "marketState": d["market_state"],
    }


SYMBOL_REGEX = re.compile(r"^[A-Z0-9.^-]{1,15}$")
QUOTE_CACHE_MINUTES = 15
CHART_CACHE_HOURS_DAILY = 24
CHART_CACHE_HOURS_INTRADAY = 1
VALID_TIMEFRAMES = {"1d", "5d", "1mo", "3mo", "1y"}


@router.get(
    "/finance/quote",
    dependencies=[Depends(rate_limit("finance-quote", 120, TEN_MIN_MS))],
)
async def get_quotes(symbols: str = Query(..., min_length=1, max_length=600)) -> dict:
    parsed_symbols = [s.strip().upper() for s in symbols.split(",") if s.strip()][:25]

    if not parsed_symbols:
        raise HTTPException(status_code=400, detail="At least one symbol is required")

    invalid = [s for s in parsed_symbols if not SYMBOL_REGEX.match(s)]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid symbols: {', '.join(invalid)}")

    try:
        clean_expired_quotes()
    except Exception:
        pass

    cached_quotes = get_cached_quotes(parsed_symbols)
    uncached_symbols = [s for s in parsed_symbols if s not in cached_quotes]

    fresh_quotes = {}
    if uncached_symbols:
        fresh_quotes = await fetch_quotes(uncached_symbols)
        for quote in fresh_quotes.values():
            set_cached_quote(quote, QUOTE_CACHE_MINUTES)

    all_quotes = {**cached_quotes, **fresh_quotes}
    return {"quotes": [_quote_to_camel(q) for q in all_quotes.values()]}


@router.get(
    "/finance/chart",
    dependencies=[Depends(rate_limit("finance-chart", 120, TEN_MIN_MS))],
)
async def get_chart(
    symbol: str = Query(..., min_length=1, max_length=15),
    timeframe: str = Query("1mo"),
) -> dict:
    if not re.match(r"^[A-Za-z0-9.^-]+$", symbol):
        raise HTTPException(status_code=400, detail="Invalid symbol")
    if timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(
            status_code=400, detail=f"timeframe must be one of: {', '.join(VALID_TIMEFRAMES)}"
        )

    normalized_symbol = symbol.upper()

    try:
        clean_expired_charts()
    except Exception:
        pass

    cached = get_cached_chart(normalized_symbol, timeframe)
    if cached:
        return {
            "symbol": normalized_symbol,
            "timeframe": timeframe,
            "data": cached["data"],
            "cached": True,
        }

    cache_ttl = (
        CHART_CACHE_HOURS_INTRADAY if timeframe in ("1d", "5d") else CHART_CACHE_HOURS_DAILY
    )

    data = await fetch_chart(normalized_symbol, timeframe)
    set_cached_chart(normalized_symbol, timeframe, data, cache_ttl)

    return {"symbol": normalized_symbol, "timeframe": timeframe, "data": data, "cached": False}


@router.get(
    "/finance/search",
    dependencies=[Depends(rate_limit("finance-search", 120, TEN_MIN_MS))],
)
async def search(query: str = Query(..., min_length=1, max_length=100)) -> dict:
    results = await search_stocks(query)
    return {"results": results}


@router.get(
    "/finance/heatmap",
    dependencies=[Depends(rate_limit("finance-heatmap", 60, TEN_MIN_MS))],
)
async def get_heatmap(
    date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    list: Optional[str] = Query(None),
) -> dict:
    if list == "true":
        return {"dates": get_available_heatmap_dates()}

    today = date_cls.today().isoformat()
    market_date = date or today

    snapshot = get_heatmap_snapshot(market_date)
    if snapshot:
        import json

        stocks = json.loads(snapshot.data)
        return {"date": snapshot.date, "stocks": stocks, "cached": True}

    if date and date != today:
        return {"date": date, "stocks": [], "cached": False}

    symbols = [s.symbol for s in SP500_STOCKS]
    quotes_map = await fetch_quotes(symbols)

    stocks = []
    sector_by_symbol = {s.symbol: s.sector for s in SP500_STOCKS}
    for symbol, quote in quotes_map.items():
        sector = sector_by_symbol.get(symbol)
        if sector:
            stocks.append({**_quote_to_camel(quote), "sector": sector})

    import json

    save_heatmap_snapshot(market_date, json.dumps(stocks))

    return {"date": market_date, "stocks": stocks, "cached": False}


@router.get(
    "/finance/watchlist",
    dependencies=[Depends(rate_limit("finance-watchlist-get", 120, TEN_MIN_MS))],
)
async def get_watchlist_with_quotes() -> dict:
    watchlist = get_watchlist()

    if not watchlist:
        return {"watchlist": []}

    symbols = [item.symbol for item in watchlist]
    cached_quotes = get_cached_quotes(symbols)
    uncached_symbols = [s for s in symbols if s not in cached_quotes]

    fresh_quotes = {}
    if uncached_symbols:
        fresh_quotes = await fetch_quotes(uncached_symbols)
        for quote in fresh_quotes.values():
            set_cached_quote(quote, QUOTE_CACHE_MINUTES)

    all_quotes = {**cached_quotes, **fresh_quotes}

    watchlist_with_quotes = [
        {
            "id": item.id,
            "symbol": item.symbol,
            "name": item.name,
            "exchange": item.exchange,
            "addedAt": item.added_at,
            "quote": _quote_to_camel(all_quotes[item.symbol]) if item.symbol in all_quotes else None,
            "loading": False,
            "error": None if item.symbol in all_quotes else f"Failed to fetch quote for {item.symbol}",
        }
        for item in watchlist
    ]

    return {"watchlist": watchlist_with_quotes}


@router.post(
    "/finance/watchlist",
    dependencies=[Depends(rate_limit("finance-watchlist-post", 60, TEN_MIN_MS))],
)
async def add_watchlist_item(body: FinanceWatchlistActionRequestBody) -> dict:
    normalized_symbol = body.symbol.upper().strip()

    if is_in_watchlist(normalized_symbol):
        raise HTTPException(status_code=409, detail="Stock already in watchlist")

    item_id = add_to_watchlist(normalized_symbol, body.name, body.exchange or "UNKNOWN")

    return {
        "success": True,
        "id": item_id,
        "message": f"{normalized_symbol} added to watchlist",
    }


@router.delete(
    "/finance/watchlist",
    dependencies=[Depends(rate_limit("finance-watchlist-delete", 60, TEN_MIN_MS))],
)
async def remove_watchlist_item(body: FinanceWatchlistDeleteRequestBody) -> dict:
    remove_from_watchlist(body.id)
    return {"success": True, "message": "Stock removed from watchlist"}
