import { NextResponse } from "next/server";
import {
  getArticleById,
  getUnsummarizedArticles,
  updateArticleSummary,
} from "@/lib/db/queries";
import { summarizeArticle } from "@/lib/ollama/client";
import { backgroundSummarize } from "@/lib/ollama/background";
import { OllamaUnavailableError } from "@/types";
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { z } from "zod";
import { badRequest, internalServerError, validationError } from "@/lib/server/api-response";
import { InvalidJsonError, parseJsonBody } from "@/lib/server/request";

const SummarizeRequestSchema = z
  .object({
    articleId: z.number().int().positive().optional(),
    category: z.string().trim().min(1).max(100).optional(),
    limit: z.number().int().min(1).max(50).optional(),
    background: z.boolean().optional(),
  })
  .strict();

export async function POST(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "summarize",
    limit: 20,
    windowMs: 5 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { articleId, category, limit = 10, background } =
      await parseJsonBody(request, SummarizeRequestSchema);

    // Trigger the full background summarizer (with content fetching)
    if (background) {
      backgroundSummarize().catch((e) =>
        console.warn("[Newsixity] Background summarization error:", e)
      );
      return NextResponse.json({
        message: "Background summarization started",
      });
    }

    // Single article summarization
    if (articleId) {
      const article = getArticleById(articleId);
      if (!article) {
        return NextResponse.json(
          { error: "Article not found" },
          { status: 404 }
        );
      }

      // If already summarized, return cached summary
      if (article.summary) {
        return NextResponse.json({ summary: article.summary });
      }

      // Use content if available, otherwise use title as fallback
      const textToSummarize = article.content && article.content.length > 10
        ? article.content
        : null;

      if (!textToSummarize) {
        return NextResponse.json(
          { error: "Article has no content to summarize" },
          { status: 400 }
        );
      }

      const summary = await summarizeArticle(article.title, textToSummarize);
      updateArticleSummary(articleId, summary, "qwen3-coder-next:cloud");

      return NextResponse.json({ summary });
    }

    // Batch summarization
    const articles = getUnsummarizedArticles(limit, category);
    let summarized = 0;
    const errors: string[] = [];

    for (const article of articles) {
      try {
        if (!article.content) {
          errors.push(`Article ${article.id}: no content to summarize`);
          continue;
        }

        const summary = await summarizeArticle(article.title, article.content);
        updateArticleSummary(article.id, summary, "llama3.2");
        summarized++;
      } catch (e) {
        if (e instanceof OllamaUnavailableError) {
          return NextResponse.json(
            {
              error: "Ollama is not available",
              summarized,
              errors,
            },
            { status: 503 }
          );
        }
        const requestId = `${Date.now()}-${article.id}`;
        console.error(
          `[Newsixity] Summarize item error [${requestId}]`,
          e instanceof Error ? e.message : String(e)
        );
        errors.push(`Article ${article.id}: failed to summarize`);
      }
    }

    return NextResponse.json({ summarized, errors });
  } catch (e) {
    if (e instanceof z.ZodError) {
      return validationError(e);
    }
    if (e instanceof InvalidJsonError) {
      return badRequest("Invalid JSON payload");
    }
    if (e instanceof OllamaUnavailableError) {
      return NextResponse.json(
        { error: "Ollama is not available" },
        { status: 503 }
      );
    }
    return internalServerError("Summarize POST error", e);
  }
}
