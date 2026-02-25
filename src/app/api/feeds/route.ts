import { NextResponse } from "next/server";
import {
  getArticlesByCategory,
  getArticleGroupsByCategory,
  searchArticles,
} from "@/lib/db/queries";
import { z } from "zod";
import { internalServerError, validationError } from "@/lib/server/api-response";
import { enforceRateLimit } from "@/lib/server/rate-limit";

const FeedsQuerySchema = z.object({
  category: z.string().trim().min(1).max(100).optional(),
  limit: z.coerce.number().int().min(1).max(200).default(50),
  offset: z.coerce.number().int().min(0).max(10000).default(0),
  grouped: z.enum(["true", "false"]).optional(),
  search: z.string().trim().min(1).max(250).optional(),
});

export async function GET(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "feeds-get",
    limit: 180,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { searchParams } = new URL(request.url);
    const { category, limit, offset, grouped, search } = FeedsQuerySchema.parse({
      category: searchParams.get("category") ?? undefined,
      limit: searchParams.get("limit") ?? undefined,
      offset: searchParams.get("offset") ?? undefined,
      grouped: searchParams.get("grouped") ?? undefined,
      search: searchParams.get("search") ?? undefined,
    });

    if (search) {
      const results = searchArticles(search, { category, limit });
      return NextResponse.json({ articles: results });
    }

    if (grouped === "true") {
      const groups = getArticleGroupsByCategory(category ?? null, { limit });
      return NextResponse.json({ groups });
    }

    const articles = getArticlesByCategory(category ?? null, { limit, offset });
    return NextResponse.json({ articles });
  } catch (e) {
    if (e instanceof z.ZodError) {
      return validationError(e);
    }
    return internalServerError("Feeds GET error", e);
  }
}
