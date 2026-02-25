import { NextResponse } from "next/server";
import { getArticleById } from "@/lib/db/queries";
import {
  getArticleResearch,
  saveArticleResearch,
  isQuotaExceeded,
  incrementQuota,
  getRemainingQuota,
  getSetting,
} from "@/lib/db/queries";
import { conductResearch } from "@/lib/research/orchestrator";
import { OllamaUnavailableError } from "@/types";
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { z } from "zod";
import { badRequest, internalServerError, validationError } from "@/lib/server/api-response";
import { InvalidJsonError, parseJsonBody } from "@/lib/server/request";

const ResearchRequestSchema = z.object({
  articleId: z.number().int().positive(),
  question: z.string().trim().min(1).max(500),
});

export async function POST(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "research",
    limit: 30,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { articleId, question } = await parseJsonBody(request, ResearchRequestSchema);

    const normalizedQuestion = question.trim();

    const article = getArticleById(articleId);
    if (!article) {
      return NextResponse.json(
        { error: "Article not found" },
        { status: 404 }
      );
    }

    // Check cache first (cached results don't count against quota)
    const cached = getArticleResearch(articleId, normalizedQuestion);
    if (cached) {
      return NextResponse.json({
        answer: cached.answer,
        sources: cached.sources,
        cached: true,
      });
    }

    // Check quota BEFORE conducting new research
    if (isQuotaExceeded()) {
      return NextResponse.json(
        {
          error: "Monthly research quota reached. The limit will reset next month.",
          quotaExceeded: true,
        },
        { status: 429 }
      );
    }

    // Get settings from DB
    const apiKey = getSetting("brave_search_api_key");
    const ollamaModel = getSetting("ollama_model") || "llama3.2";

    // Conduct research
    const { answer, sources } = await conductResearch(
      article.title,
      article.content,
      normalizedQuestion,
      ollamaModel,
      apiKey
    );

    // Increment quota after successful search
    const newCount = incrementQuota();
    console.log(`[Newsixity] Search quota: ${newCount}/1900 used this month`);

    // Cache result
    saveArticleResearch(
      articleId,
      normalizedQuestion,
      answer,
      sources,
      ollamaModel
    );

    return NextResponse.json({
      answer,
      sources,
      cached: false,
      quotaRemaining: getRemainingQuota(),
    });
  } catch (e) {
    if (e instanceof z.ZodError) {
      return validationError(e);
    }
    if (e instanceof InvalidJsonError) {
      return badRequest("Invalid JSON payload");
    }

    if (e instanceof OllamaUnavailableError) {
      return NextResponse.json(
        { error: "Ollama is not available. Make sure Ollama is running locally." },
        { status: 503 }
      );
    }
    return internalServerError("Research POST error", e);
  }
}
