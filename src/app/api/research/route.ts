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

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { articleId, question } = body as {
      articleId?: number;
      question?: string;
    };

    if (!articleId || !question?.trim()) {
      return NextResponse.json(
        { error: "articleId and question are required" },
        { status: 400 }
      );
    }

    const article = getArticleById(articleId);
    if (!article) {
      return NextResponse.json(
        { error: "Article not found" },
        { status: 404 }
      );
    }

    // Check cache first (cached results don't count against quota)
    const cached = getArticleResearch(articleId, question.trim());
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
      question.trim(),
      ollamaModel,
      apiKey
    );

    // Increment quota after successful search
    const newCount = incrementQuota();
    console.log(`[Newsixity] Search quota: ${newCount}/1900 used this month`);

    // Cache result
    saveArticleResearch(
      articleId,
      question.trim(),
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
    if (e instanceof OllamaUnavailableError) {
      return NextResponse.json(
        { error: "Ollama is not available. Make sure Ollama is running locally." },
        { status: 503 }
      );
    }
    const message = e instanceof Error ? e.message : String(e);
    console.error("[Newsixity] Research error:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
