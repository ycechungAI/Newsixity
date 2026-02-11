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

export async function GET() {
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
      for (const [symbol, quote] of freshQuotes) {
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
    const message = e instanceof Error ? e.message : String(e);
    console.error("[Newsixity] Watchlist fetch error:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { symbol, name, exchange } = body;

    if (!symbol || !name) {
      return NextResponse.json(
        { error: "Symbol and name are required" },
        { status: 400 }
      );
    }

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
    const message = e instanceof Error ? e.message : String(e);
    console.error("[Newsixity] Add to watchlist error:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function DELETE(request: Request) {
  try {
    const body = await request.json();
    const { id } = body;

    if (!id) {
      return NextResponse.json(
        { error: "ID is required" },
        { status: 400 }
      );
    }

    removeFromWatchlist(id);

    return NextResponse.json({
      success: true,
      message: "Stock removed from watchlist",
    });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    console.error("[Newsixity] Remove from watchlist error:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
