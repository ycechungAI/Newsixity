import { NextResponse } from "next/server";
import {
  getWatchlist,
  addToWatchlist,
  removeFromWatchlist,
  isInWatchlist,
  getCachedQuotes,
} from "@/lib/db/queries";
import { fetchYahooQuotes } from "@/lib/finance/yahoo";
import { QUOTE_CACHE_MINUTES } from "@/lib/finance/constants";
import { setCachedQuote } from "@/lib/db/queries";
import { z } from "zod";
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { badRequest, internalServerError, validationError } from "@/lib/server/api-response";
import { InvalidJsonError, parseJsonBody } from "@/lib/server/request";

const WatchlistCreateSchema = z
  .object({
    symbol: z
      .string()
      .trim()
      .min(1)
      .max(15)
      .regex(/^[A-Z0-9.^-]+$/i, "Invalid symbol"),
    name: z.string().trim().min(1).max(200),
    exchange: z.string().trim().min(1).max(64).optional(),
  })
  .strict();

const WatchlistDeleteSchema = z
  .object({
    id: z.number().int().positive(),
  })
  .strict();

export async function GET(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "finance-watchlist-get",
    limit: 120,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const watchlist = getWatchlist();

    if (watchlist.length === 0) {
      return NextResponse.json({ watchlist: [] });
    }

    // Get symbols from watchlist
    const symbols = watchlist.map((item) => item.symbol);

    // Check cache first
    const cachedQuotes = getCachedQuotes(symbols);
    const uncachedSymbols = symbols.filter((s) => !cachedQuotes.has(s));

    // Fetch missing quotes
    let freshQuotes = new Map();
    if (uncachedSymbols.length > 0) {
      freshQuotes = await fetchYahooQuotes(uncachedSymbols);

      // Cache fresh quotes
      for (const [, quote] of freshQuotes) {
        setCachedQuote(quote, QUOTE_CACHE_MINUTES);
      }
    }

    // Combine cached and fresh quotes
    const allQuotes = new Map([...cachedQuotes, ...freshQuotes]);

    // Build watchlist items with quotes
    const watchlistWithQuotes = watchlist.map((item) => ({
      ...item,
      quote: allQuotes.get(item.symbol) || null,
      loading: false,
      error: allQuotes.has(item.symbol) ? null : `Failed to fetch quote for ${item.symbol}`,
    }));

    return NextResponse.json({ watchlist: watchlistWithQuotes });
  } catch (e) {
    return internalServerError("Watchlist GET error", e);
  }
}

export async function POST(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "finance-watchlist-post",
    limit: 60,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { symbol, name, exchange } = await parseJsonBody(request, WatchlistCreateSchema);

    const normalizedSymbol = symbol.toUpperCase().trim();

    // Check if already in watchlist
    if (isInWatchlist(normalizedSymbol)) {
      return NextResponse.json(
        { error: "Stock already in watchlist" },
        { status: 409 }
      );
    }

    // Add to watchlist
    const id = addToWatchlist(normalizedSymbol, name, exchange || "UNKNOWN");

    return NextResponse.json({
      success: true,
      id,
      message: `${normalizedSymbol} added to watchlist`,
    });
  } catch (e) {
    if (e instanceof z.ZodError) {
      return validationError(e);
    }
    if (e instanceof InvalidJsonError) {
      return badRequest("Invalid JSON payload");
    }
    return internalServerError("Watchlist POST error", e);
  }
}

export async function DELETE(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "finance-watchlist-delete",
    limit: 60,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { id } = await parseJsonBody(request, WatchlistDeleteSchema);

    removeFromWatchlist(id);

    return NextResponse.json({
      success: true,
      message: "Stock removed from watchlist",
    });
  } catch (e) {
    if (e instanceof z.ZodError) {
      return validationError(e);
    }
    if (e instanceof InvalidJsonError) {
      return badRequest("Invalid JSON payload");
    }
    return internalServerError("Watchlist DELETE error", e);
  }
}
