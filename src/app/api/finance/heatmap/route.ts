import { NextRequest, NextResponse } from 'next/server';
import { getHeatmapSnapshot, saveHeatmapSnapshot, getAvailableHeatmapDates } from '@/lib/db/queries';
import { fetchYahooQuotes } from '@/lib/finance/yahoo';
import { SP500_STOCKS } from '@/lib/finance/sp500';
import type { HeatmapStock } from '@/lib/finance/types';
import { z } from "zod";

export const dynamic = 'force-dynamic';
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { internalServerError, validationError } from "@/lib/server/api-response";

const HeatmapQuerySchema = z.object({
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "date must be YYYY-MM-DD").optional(),
  list: z.enum(["true", "false"]).optional(),
});

// GET /api/finance/heatmap?date=YYYY-MM-DD
// Returns heatmap data for a specific date (defaults to today)
export async function GET(request: NextRequest) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "finance-heatmap",
    limit: 60,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { searchParams } = new URL(request.url);
    const { date: requestedDate, list } = HeatmapQuerySchema.parse({
      date: searchParams.get("date") ?? undefined,
      list: searchParams.get("list") ?? undefined,
    });
    const listDates = list === "true";

    // If list=true, return available dates
    if (listDates) {
      const dates = getAvailableHeatmapDates();
      return NextResponse.json({ dates });
    }

    // Get current market date (YYYY-MM-DD)
    const today = new Date();
    const marketDate = requestedDate || formatDate(today);

    // Check if snapshot exists in database
    const snapshot = getHeatmapSnapshot(marketDate);

    if (snapshot) {
      // Return cached snapshot
      const stocks: HeatmapStock[] = JSON.parse(snapshot.data);
      return NextResponse.json({
        date: snapshot.date,
        stocks,
        cached: true,
      });
    }

    // If requesting historical date that doesn't exist, return empty
    if (requestedDate && requestedDate !== formatDate(today)) {
      return NextResponse.json({
        date: requestedDate,
        stocks: [],
        cached: false,
      });
    }

    // Fetch fresh data from Yahoo Finance (only for today)
    const symbols = SP500_STOCKS.map((s) => s.symbol);
    const quotesMap = await fetchYahooQuotes(symbols);

    // Combine quotes with sector information
    const stocks: HeatmapStock[] = [];
    quotesMap.forEach((quote, symbol) => {
      const stockInfo = SP500_STOCKS.find((s) => s.symbol === symbol);
      if (stockInfo) {
        stocks.push({
          ...quote,
          sector: stockInfo.sector,
        });
      }
    });

    // Save snapshot to database
    const data = JSON.stringify(stocks);
    saveHeatmapSnapshot(marketDate, data);

    return NextResponse.json({
      date: marketDate,
      stocks,
      cached: false,
    });
  } catch (error) {
    if (error instanceof z.ZodError) {
      return validationError(error);
    }
    return internalServerError("Finance heatmap GET error", error);
  }
}

function formatDate(date: Date): string {
  return date.toISOString().split('T')[0];
}
