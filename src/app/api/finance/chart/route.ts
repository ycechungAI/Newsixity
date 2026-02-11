import { NextResponse } from "next/server";
import { fetchYahooChart } from "@/lib/finance/yahoo";
import {
  getCachedChart,
  setCachedChart,
  cleanExpiredCharts,
} from "@/lib/db/queries";
import {
  CHART_CACHE_HOURS_DAILY,
  CHART_CACHE_HOURS_INTRADAY,
} from "@/lib/finance/constants";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const symbol = searchParams.get("symbol");
    const timeframe = searchParams.get("timeframe") || "1mo";

    if (!symbol) {
      return NextResponse.json(
        { error: "Symbol parameter is required" },
        { status: 400 }
      );
    }

    const validTimeframes = ["1d", "5d", "1mo", "3mo", "1y"];
    if (!validTimeframes.includes(timeframe)) {
      return NextResponse.json(
        { error: "Invalid timeframe. Must be one of: 1d, 5d, 1mo, 3mo, 1y" },
        { status: 400 }
      );
    }

    // Clean expired cache entries (opportunistic cleanup)
    try {
      cleanExpiredCharts();
    } catch {
      // Ignore cleanup errors
    }

    // Check cache first
    const cached = getCachedChart(symbol.toUpperCase(), timeframe);
    if (cached) {
      return NextResponse.json({
        symbol: symbol.toUpperCase(),
        timeframe,
        data: cached.data,
        cached: true,
      });
    }

    // Calculate date range based on timeframe
    const period2 = new Date();
    let period1 = new Date();
    let interval: '1d' | '1h' | '5m' = '1d';
    let cacheTTL = CHART_CACHE_HOURS_DAILY;

    switch (timeframe) {
      case '1d':
        period1.setDate(period1.getDate() - 1);
        interval = '5m';
        cacheTTL = CHART_CACHE_HOURS_INTRADAY;
        break;
      case '5d':
        period1.setDate(period1.getDate() - 5);
        interval = '1h';
        cacheTTL = CHART_CACHE_HOURS_INTRADAY;
        break;
      case '1mo':
        period1.setMonth(period1.getMonth() - 1);
        break;
      case '3mo':
        period1.setMonth(period1.getMonth() - 3);
        break;
      case '1y':
        period1.setFullYear(period1.getFullYear() - 1);
        break;
    }

    // Fetch from Yahoo Finance
    const data = await fetchYahooChart(
      symbol.toUpperCase(),
      period1,
      period2,
      interval
    );

    // Cache the result
    setCachedChart(symbol.toUpperCase(), timeframe, data, cacheTTL);

    return NextResponse.json({
      symbol: symbol.toUpperCase(),
      timeframe,
      data,
      cached: false,
    });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    console.error("[Newsixity] Chart fetch error:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
