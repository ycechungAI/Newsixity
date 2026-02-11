import { NextResponse } from "next/server";
import {
  getArticleById,
  getUnsummarizedArticles,
  updateArticleSummary,
} from "@/lib/db/queries";
import { summarizeArticle } from "@/lib/ollama/client";
import { backgroundSummarize } from "@/lib/ollama/background";
import { OllamaUnavailableError } from "@/types";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { articleId, category, limit = 10, background } = body as {
      articleId?: number;
      category?: string;
      limit?: number;
      background?: boolean;
    };

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
      updateArticleSummary(articleId, summary, "llama3.2");

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
        const message = e instanceof Error ? e.message : String(e);
        errors.push(`Article ${article.id}: ${message}`);
      }
    }

    return NextResponse.json({ summarized, errors });
  } catch (e) {
    if (e instanceof OllamaUnavailableError) {
      return NextResponse.json(
        { error: "Ollama is not available" },
        { status: 503 }
      );
    }
    const message = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
