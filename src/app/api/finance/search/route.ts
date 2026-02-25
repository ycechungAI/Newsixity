import { NextResponse } from "next/server";
import { searchYahooStocks } from "@/lib/finance/yahoo";
import { z } from "zod";
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { internalServerError, validationError } from "@/lib/server/api-response";

const FinanceSearchQuerySchema = z.object({
  query: z.string().trim().min(1).max(100),
});

export async function GET(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "finance-search",
    limit: 120,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { searchParams } = new URL(request.url);
    const { query } = FinanceSearchQuerySchema.parse({
      query: searchParams.get("query") ?? undefined,
    });

    const results = await searchYahooStocks(query);

    return NextResponse.json({ results });
  } catch (e) {
    if (e instanceof z.ZodError) {
      return validationError(e);
    }
    return internalServerError("Finance search GET error", e);
  }
}
