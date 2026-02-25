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
import { z } from "zod";
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { internalServerError, validationError } from "@/lib/server/api-response";

const FinanceChartQuerySchema = z.object({
  symbol: z.string().trim().min(1).max(15).regex(/^[A-Z0-9.^-]+$/i, "Invalid symbol"),
  timeframe: z.enum(["1d", "5d", "1mo", "3mo", "1y"]).default("1mo"),
});

export async function GET(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "finance-chart",
    limit: 120,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { searchParams } = new URL(request.url);
    const { symbol, timeframe } = FinanceChartQuerySchema.parse({
      symbol: searchParams.get("symbol") ?? undefined,
      timeframe: searchParams.get("timeframe") ?? undefined,
    });
    const normalizedSymbol = symbol.toUpperCase();

    // Clean expired cache entries (opportunistic cleanup)
    try {
      cleanExpiredCharts();
    } catch {
      // Ignore cleanup errors
    }

    // Check cache first
    const cached = getCachedChart(normalizedSymbol, timeframe);
    if (cached) {
      return NextResponse.json({
        symbol: normalizedSymbol,
        timeframe,
        data: cached.data,
        cached: true,
      });
    }

    // Calculate date range based on timeframe
    const period2 = new Date();
    const period1 = new Date();
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
      normalizedSymbol,
      period1,
      period2,
      interval
    );

    // Cache the result
    setCachedChart(normalizedSymbol, timeframe, data, cacheTTL);

    return NextResponse.json({
      symbol: normalizedSymbol,
      timeframe,
      data,
      cached: false,
    });
  } catch (e) {
    if (e instanceof z.ZodError) {
      return validationError(e);
    }
    return internalServerError("Finance chart GET error", e);
  }
}
