import { NextResponse } from "next/server";
import { getAllArticleResearch, deleteArticleResearch } from "@/lib/db/queries";
import { z } from "zod";
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { internalServerError, validationError } from "@/lib/server/api-response";

const ResearchHistoryGetQuerySchema = z.object({
  articleId: z.coerce.number().int().positive(),
});

const ResearchHistoryDeleteQuerySchema = z.object({
  id: z.coerce.number().int().positive(),
});

export async function GET(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "research-history-get",
    limit: 120,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { searchParams } = new URL(request.url);
    const { articleId } = ResearchHistoryGetQuerySchema.parse({
      articleId: searchParams.get("articleId"),
    });

    // Get all research for this article
    const history = getAllArticleResearch(articleId);

    return NextResponse.json({
      history: history.map((item) => ({
        id: item.id,
        question: item.question,
        answer: item.answer,
        sources: item.sources,
        createdAt: item.createdAt,
      })),
    });
  } catch (e) {
    if (e instanceof z.ZodError) {
      return validationError(e);
    }
    return internalServerError("Research history GET error", e);
  }
}

export async function DELETE(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "research-history-delete",
    limit: 120,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { searchParams } = new URL(request.url);
    const { id: researchId } = ResearchHistoryDeleteQuerySchema.parse({
      id: searchParams.get("id"),
    });

    // Delete the research item
    deleteArticleResearch(researchId);

    return NextResponse.json({
      success: true,
      message: "Research deleted successfully",
    });
  } catch (e) {
    if (e instanceof z.ZodError) {
      return validationError(e);
    }
    return internalServerError("Research history DELETE error", e);
  }
}
