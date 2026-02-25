import { NextResponse } from "next/server";
import { seedAllFeeds } from "@/lib/rss/feeds";
import { fetchAllFeeds } from "@/lib/rss/parser";
import {
  upsertArticle,
  getArticleByTitleHash,
  getArticlesByCategory,
  getArticleById,
  getFeedCategorySlug,
} from "@/lib/db/queries";
import { hashTitle, isDuplicate } from "@/lib/dedup/similarity";
import { groupArticles } from "@/lib/dedup/grouping";
import { backgroundSummarize } from "@/lib/ollama/background";
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { z } from "zod";
import { badRequest, validationError } from "@/lib/server/api-response";
import { InvalidJsonError, parseOptionalJsonBody } from "@/lib/server/request";
import type { Article, RefreshResult } from "@/types";

const RefreshRequestSchema = z
  .object({
    category: z.string().trim().min(1).max(100).optional(),
  })
  .strict();

export async function POST(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "feeds-refresh",
    limit: 6,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const body = await parseOptionalJsonBody(request, RefreshRequestSchema);
    const category = body?.category;

    // Ensure all default feeds exist in the database
    await seedAllFeeds();

    // Fetch articles from all enabled feeds
    const feedResults = await fetchAllFeeds();

    let refreshed = 0;
    let newArticles = 0;
    const errors: string[] = [];

    // Track new articles per category for grouping
    const newArticlesByCategory = new Map<string, Article[]>();
    const existingArticlesByCategory = new Map<string, Article[]>();

    for (const feedResult of feedResults) {
      if (feedResult.error) {
        errors.push(`Feed ${feedResult.feedUrl}: ${feedResult.error}`);
        continue;
      }

      refreshed++;

      // Look up the category slug for this feed
      const categorySlug = getFeedCategorySlug(feedResult.feedId);
      if (!categorySlug) {
        errors.push(`Feed ${feedResult.feedUrl}: could not determine category`);
        continue;
      }

      // If a category filter was provided, skip feeds not in that category
      if (category && categorySlug !== category) {
        continue;
      }

      // Get existing articles in this category for fuzzy dedup (memoized per category).
      let existingArticles = existingArticlesByCategory.get(categorySlug);
      if (!existingArticles) {
        existingArticles = getArticlesByCategory(categorySlug, { limit: 200 });
        existingArticlesByCategory.set(categorySlug, existingArticles);
      }

      for (const article of feedResult.articles) {
        const titleHash = hashTitle(article.title);

        // Check for exact title hash duplicate
        const existingByHash = getArticleByTitleHash(titleHash, categorySlug);
        if (existingByHash) {
          continue;
        }

        // Check for fuzzy duplicate against existing article titles
        const isFuzzyDup = existingArticles.some((existing) =>
          isDuplicate(article.title, existing.title)
        );
        if (isFuzzyDup) {
          continue;
        }

        // Insert the article
        const insertedId = upsertArticle(
          feedResult.feedId,
          article,
          titleHash
        );

        if (insertedId !== null) {
          newArticles++;
          const inserted = getArticleById(insertedId);
          if (inserted) {
            existingArticles.push(inserted);
            if (!newArticlesByCategory.has(categorySlug)) {
              newArticlesByCategory.set(categorySlug, []);
            }
            newArticlesByCategory.get(categorySlug)!.push(inserted);
          }
        }
      }
    }

    // Group new articles per category
    for (const [slug, articles] of newArticlesByCategory) {
      try {
        groupArticles(articles, slug);
      } catch {
        errors.push(`Grouping error for ${slug}`);
      }
    }

    // Score and promote articles for capped categories
    try {
      const { scoreAndPromoteAll } = await import("@/lib/ranking/promoter");
      scoreAndPromoteAll();
    } catch {
      errors.push("Scoring/promotion error");
    }

    // Fire-and-forget background summarization after refresh
    backgroundSummarize(10).catch((e) =>
      console.warn("[Newsixity] Background summarization error:", e)
    );

    const result: RefreshResult = { refreshed, newArticles, errors };
    return NextResponse.json(result);
  } catch (e) {
    if (e instanceof z.ZodError) {
      return validationError(e);
    }
    if (e instanceof InvalidJsonError) {
      return badRequest("Invalid JSON payload");
    }
    const requestId = `${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
    console.error(
      `[Newsixity] Feeds refresh POST error [${requestId}]`,
      e instanceof Error ? e.message : String(e)
    );
    return NextResponse.json(
      {
        refreshed: 0,
        newArticles: 0,
        errors: [`Internal server error (${requestId})`],
      },
      { status: 500 }
    );
  }
}
