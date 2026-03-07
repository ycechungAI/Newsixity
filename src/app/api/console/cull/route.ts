import { NextResponse } from "next/server";
import {
  getSummarizationQueueCount,
  cullUnsummarizedQueueToLimit,
  MAX_UNSUMMARIZED_QUEUE,
} from "@/lib/db/queries";
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { internalServerError } from "@/lib/server/api-response";

// POST /api/console/cull
// One-time cull: reduce unsummarized queue to 2000 (or custom limit). Returns counts.
export async function POST(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "console-cull",
    limit: 10,
    windowMs: 60 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const before = getSummarizationQueueCount();
    const limit =
      Number(new URL(request.url).searchParams.get("limit")) ||
      MAX_UNSUMMARIZED_QUEUE;

    const culled = cullUnsummarizedQueueToLimit(limit);
    const after = getSummarizationQueueCount();

    return NextResponse.json({
      culled,
      queueCountBefore: before,
      queueCountAfter: after,
      limit,
    });
  } catch (error) {
    return internalServerError("Console cull error", error);
  }
}
