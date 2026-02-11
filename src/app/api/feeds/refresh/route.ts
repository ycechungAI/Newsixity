import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { seedAllFeeds } from "@/lib/rss/feeds";
import { fetchAllFeeds } from "@/lib/rss/parser";
import {
  upsertArticle,
  getArticleByTitleHash,
  getArticlesByCategory,
  getArticleById,
} from "@/lib/db/queries";
import { hashTitle, isDuplicate } from "@/lib/dedup/similarity";
import { groupArticles } from "@/lib/dedup/grouping";
import { backgroundSummarize } from "@/lib/ollama/background";
import type { Article, RefreshResult } from "@/types";

export async function POST(request: Request) {
  try {
    let category: string | undefined;
    try {
      const body = await request.json();
      category = body.category;
    } catch {
      // Body might be empty, that's fine
    }

    // Ensure all default feeds exist in the database
    await seedAllFeeds();

    // Fetch articles from all enabled feeds
    const feedResults = await fetchAllFeeds();

    let refreshed = 0;
    let newArticles = 0;
    const errors: string[] = [];

    // Track new articles per category for grouping
    const newArticlesByCategory = new Map<string, Article[]>();

    for (const feedResult of feedResults) {
      if (feedResult.error) {
        errors.push(`Feed ${feedResult.feedUrl}: ${feedResult.error}`);
        continue;
      }

      refreshed++;

      // Look up the category slug for this feed
      const feedCategory = getDb()
        .prepare(
          `SELECT c.slug FROM feeds f JOIN categories c ON f.category_id = c.id WHERE f.id = ?`
        )
        .get(feedResult.feedId) as { slug: string } | undefined;

      if (!feedCategory) {
        errors.push(`Feed ${feedResult.feedUrl}: could not determine category`);
        continue;
      }

      const categorySlug = feedCategory.slug;

      // If a category filter was provided, skip feeds not in that category
      if (category && categorySlug !== category) {
        continue;
      }

      // Get existing articles in this category for fuzzy dedup
      const existingArticles = getArticlesByCategory(categorySlug, {
        limit: 200,
      });

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
      } catch (e) {
        const message =
          e instanceof Error ? e.message : String(e);
        errors.push(`Grouping error for ${slug}: ${message}`);
      }
    }

    // Fire-and-forget background summarization after refresh
    backgroundSummarize(10).catch((e) =>
      console.warn("[Newsixity] Background summarization error:", e)
    );

    const result: RefreshResult = { refreshed, newArticles, errors };
    return NextResponse.json(result);
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      { refreshed: 0, newArticles: 0, errors: [message] },
      { status: 500 }
    );
  }
}
