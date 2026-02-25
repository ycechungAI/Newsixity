import { NextResponse } from "next/server";
import { createManualArticle, deleteManualArticle } from "@/lib/db/queries";
import { z } from "zod";
import { stripHtml } from "@/lib/utils/sanitize";
import { internalServerError, validationError } from "@/lib/server/api-response";
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { parseJsonBody } from "@/lib/server/request";

const HttpUrlSchema = z
  .string()
  .url("Invalid URL")
  .refine((url) => /^https?:\/\//i.test(url), {
    message: "URL must use http:// or https://",
  });

const ManualArticleSchema = z.object({
  url: HttpUrlSchema,
  title: z.string().min(1, "Title required").max(500),
  content: z.string().max(50000).optional(),
  imageUrl: HttpUrlSchema.optional(),
  author: z.string().optional(),
});

const ManualArticleDeleteQuerySchema = z.object({
  id: z.coerce.number().int().positive(),
});

export async function POST(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "manual-article-post",
    limit: 60,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const validated = await parseJsonBody(request, ManualArticleSchema);

    const sanitized = {
      ...validated,
      title: stripHtml(validated.title).slice(0, 500),
      content: validated.content ? stripHtml(validated.content).slice(0, 8000) : undefined,
      author: validated.author ? stripHtml(validated.author).slice(0, 200) : undefined,
    };

    const articleId = createManualArticle(sanitized);

    if (!articleId) {
      return NextResponse.json(
        { error: "Article with this URL already exists" },
        { status: 409 }
      );
    }

    return NextResponse.json({ success: true, articleId }, { status: 201 });

  } catch (error) {
    if (error instanceof z.ZodError) {
      return validationError(error);
    }
    return internalServerError("Manual article POST error", error);
  }
}

export async function DELETE(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "manual-article-delete",
    limit: 60,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { searchParams } = new URL(request.url);
    const { id } = ManualArticleDeleteQuerySchema.parse({
      id: searchParams.get("id"),
    });

    const deleted = deleteManualArticle(id);

    if (!deleted) {
      return NextResponse.json(
        { error: "Article not found or not a manual link" },
        { status: 404 }
      );
    }

    return NextResponse.json({ success: true });

  } catch (error) {
    if (error instanceof z.ZodError) {
      return validationError(error);
    }
    return internalServerError("Manual article DELETE error", error);
  }
}
