import { NextResponse } from "next/server";
import { markAllReadByCategory } from "@/lib/db/queries";
import { z } from "zod";
import { badRequest, internalServerError, validationError } from "@/lib/server/api-response";
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { InvalidJsonError, parseOptionalJsonBody } from "@/lib/server/request";

const MarkAllReadSchema = z
  .object({
    category: z.string().trim().min(1).max(100).nullable().optional(),
  })
  .strict();

export async function POST(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "articles-mark-all-read",
    limit: 60,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const parsedBody = await parseOptionalJsonBody(request, MarkAllReadSchema);
    const category = parsedBody?.category ?? null;

    const count = markAllReadByCategory(category);
    return NextResponse.json({ success: true, marked: count, category });
  } catch (e) {
    if (e instanceof z.ZodError) {
      return validationError(e);
    }
    if (e instanceof InvalidJsonError) {
      return badRequest("Invalid JSON payload");
    }
    return internalServerError("Mark all read POST error", e);
  }
}
