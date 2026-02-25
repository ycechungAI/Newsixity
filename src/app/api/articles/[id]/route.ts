import { NextResponse } from "next/server";
import {
  getArticleById,
  markArticleRead,
  markArticleUnread,
  toggleArticleSaved,
} from "@/lib/db/queries";
import { summarizeArticleById } from "@/lib/ollama/background";
import { z } from "zod";
import { badRequest, internalServerError, validationError } from "@/lib/server/api-response";
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { InvalidJsonError, parseJsonBody } from "@/lib/server/request";

const IdParamSchema = z.object({
  id: z.coerce.number().int().positive(),
});

const ArticlePatchSchema = z
  .object({
    is_read: z.boolean().optional(),
    is_saved: z.boolean().optional(),
  })
  .strict()
  .refine((value) => value.is_read !== undefined || value.is_saved !== undefined, {
    message: "At least one of is_read or is_saved must be provided",
  });

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "article-get",
    limit: 240,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { id: idParam } = await params;
    const { id } = IdParamSchema.parse({ id: idParam });

    const article = getArticleById(id);
    if (!article) {
      return NextResponse.json({ error: "Article not found" }, { status: 404 });
    }

    markArticleRead(id);

    return NextResponse.json(article);
  } catch (e) {
    if (e instanceof z.ZodError) {
      return validationError(e);
    }
    return internalServerError("Article GET error", e);
  }
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "article-patch",
    limit: 120,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { id: idParam } = await params;
    const { id } = IdParamSchema.parse({ id: idParam });

    const { is_read, is_saved } = await parseJsonBody(request, ArticlePatchSchema);

    const existing = getArticleById(id);
    if (!existing) {
      return NextResponse.json({ error: "Article not found" }, { status: 404 });
    }

    if (is_read === true) {
      markArticleRead(id);
    } else if (is_read === false) {
      markArticleUnread(id);
    }

    if (is_saved !== undefined) {
      const shouldToggle = existing.isSaved !== is_saved;
      if (shouldToggle) {
        toggleArticleSaved(id);
      }

      // Get article after toggle to check current state
      const article = getArticleById(id);

      if (article) {
        // When saving, fire-and-forget a background summarization
        // so the summary is ready for the user next time
        if (article.isSaved && !article.summary) {
          summarizeArticleById(id).catch(() => {});
        }

        // Trigger preference rebuild (debounced to max once per 5 min)
        try {
          const { triggerPreferenceRebuild } = await import("@/lib/ranking/preferences");
          triggerPreferenceRebuild(article.categorySlug);
        } catch {
          // Non-critical, silently fail
        }
      }
    }

    // Return categorySlug so the client can update sidebar counts
    const article = getArticleById(id);
    return NextResponse.json({
      success: true,
      categorySlug: article?.categorySlug ?? null,
    });
  } catch (e) {
    if (e instanceof z.ZodError) {
      return validationError(e);
    }
    if (e instanceof InvalidJsonError) {
      return badRequest("Invalid JSON payload");
    }
    return internalServerError("Article PATCH error", e);
  }
}
