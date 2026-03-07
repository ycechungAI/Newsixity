import { NextResponse } from "next/server";
import { removeArticleFromQueue } from "@/lib/db/queries";
import { z } from "zod";
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { internalServerError, validationError } from "@/lib/server/api-response";

const QuerySchema = z.object({
  id: z.coerce.number().int().positive(),
});

export async function DELETE(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "console-queue-remove",
    limit: 100,
    windowMs: 60 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { searchParams } = new URL(request.url);
    const { id } = QuerySchema.parse({
      id: searchParams.get("id"),
    });

    removeArticleFromQueue(id);

    return NextResponse.json({ success: true, removedId: id });
  } catch (error) {
    if (error instanceof z.ZodError) {
      return validationError(error);
    }
    return internalServerError("Console queue removal error", error);
  }
}
