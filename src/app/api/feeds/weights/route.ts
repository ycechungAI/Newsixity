import { NextResponse } from "next/server";
import { getAllFeeds, updateFeedSourceWeight } from "@/lib/db/queries";
import { z } from "zod";
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { badRequest, internalServerError, validationError } from "@/lib/server/api-response";
import { InvalidJsonError, parseJsonBody } from "@/lib/server/request";

const FeedWeightPatchSchema = z
  .object({
    feedId: z.number().int().positive(),
    weight: z.number().min(0.1).max(2.0),
  })
  .strict();

export async function GET() {
  try {
    const feeds = getAllFeeds();
    // Add categorySlug to each feed for filtering in UI
    const feedsWithCategory = feeds.map((feed) => ({
      ...feed,
      categorySlug: feed.categorySlug ?? null,
    }));
    return NextResponse.json({ feeds: feedsWithCategory });
  } catch (e) {
    return internalServerError("Feed weights GET error", e);
  }
}

export async function PATCH(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "feeds-weights-patch",
    limit: 60,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { feedId, weight } = await parseJsonBody(request, FeedWeightPatchSchema);

    updateFeedSourceWeight(feedId, weight);

    return NextResponse.json({ success: true });
  } catch (e) {
    if (e instanceof z.ZodError) {
      return validationError(e);
    }
    if (e instanceof InvalidJsonError) {
      return badRequest("Invalid JSON payload");
    }
    return internalServerError("Feed weights PATCH error", e);
  }
}
