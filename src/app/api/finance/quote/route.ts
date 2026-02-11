import { NextResponse } from "next/server";
import { fetchYahooQuotes } from "@/lib/finance/yahoo";
import {
  getCachedQuotes,
  setCachedQuote,
  cleanExpiredQuotes,
} from "@/lib/db/queries";
import { QUOTE_CACHE_MINUTES } from "@/lib/finance/constants";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const symbolsParam = searchParams.get("symbols");

    if (!symbolsParam) {
      return NextResponse.json(
        { error: "Symbols parameter is required" },
        { status: 400 }
      );
    }

    const symbols = symbolsParam
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter((s) => s.length > 0);

    if (symbols.length === 0) {
      return NextResponse.json(
        { error: "At least one symbol is required" },
        { status: 400 }
      );
    }

    // Clean expired cache entries (opportunistic cleanup)
    try {
      cleanExpiredQuotes();
    } catch {
      // Ignore cleanup errors
    }

    // Check cache for each symbol
    const cachedQuotes = getCachedQuotes(symbols);
    const uncachedSymbols = symbols.filter((s) => !cachedQuotes.has(s));

    // Fetch missing quotes from Yahoo Finance
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
    const quotes = Array.from(allQuotes.values());

    return NextResponse.json({ quotes });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    console.error("[Newsixity] Quote fetch error:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
