import { NextResponse } from "next/server";
import { fetchYahooQuotes } from "@/lib/finance/yahoo";
import {
  getCachedQuotes,
  setCachedQuote,
  cleanExpiredQuotes,
} from "@/lib/db/queries";
import { QUOTE_CACHE_MINUTES } from "@/lib/finance/constants";
import { z } from "zod";
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { badRequest, internalServerError, validationError } from "@/lib/server/api-response";

const FinanceQuoteQuerySchema = z.object({
  symbols: z.string().trim().min(1).max(600),
});

const SYMBOL_REGEX = /^[A-Z0-9.^-]{1,15}$/;

export async function GET(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "finance-quote",
    limit: 120,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { searchParams } = new URL(request.url);
    const { symbols: symbolsParam } = FinanceQuoteQuerySchema.parse({
      symbols: searchParams.get("symbols") ?? undefined,
    });

    const symbols = symbolsParam
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter((s) => s.length > 0)
      .slice(0, 25);

    if (symbols.length === 0) {
      return badRequest("At least one symbol is required");
    }

    const invalidSymbols = symbols.filter((symbol) => !SYMBOL_REGEX.test(symbol));
    if (invalidSymbols.length > 0) {
      return badRequest(`Invalid symbols: ${invalidSymbols.join(", ")}`);
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
      for (const [, quote] of freshQuotes) {
        setCachedQuote(quote, QUOTE_CACHE_MINUTES);
      }
    }

    // Combine cached and fresh quotes
    const allQuotes = new Map([...cachedQuotes, ...freshQuotes]);
    const quotes = Array.from(allQuotes.values());

    return NextResponse.json({ quotes });
  } catch (e) {
    if (e instanceof z.ZodError) {
      return validationError(e);
    }
    return internalServerError("Finance quote GET error", e);
  }
}
