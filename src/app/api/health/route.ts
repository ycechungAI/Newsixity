import { NextResponse } from "next/server";
import {
  getCategories,
  getAllFeeds,
} from "@/lib/db/queries";
import { isOllamaAvailable, getAvailableModels } from "@/lib/ollama/client";
import type { HealthStatus } from "@/types";

export async function GET() {
  let dbHealthy = false;
  let feedsCount = 0;
  let articlesCount = 0;
  let lastRefresh: string | null = null;

  // Check database
  try {
    getCategories();
    dbHealthy = true;

    const feeds = getAllFeeds();
    feedsCount = feeds.length;

    // Find the most recent lastFetchedAt across all feeds
    for (const feed of feeds) {
      if (
        feed.lastFetchedAt &&
        (lastRefresh === null || feed.lastFetchedAt > lastRefresh)
      ) {
        lastRefresh = feed.lastFetchedAt;
      }
    }

    // Use a count query for accuracy
    const { getDb } = await import("@/lib/db");
    const countRow = getDb()
      .prepare("SELECT COUNT(*) as count FROM articles")
      .get() as { count: number };
    articlesCount = countRow.count;
  } catch {
    // DB is not healthy, defaults remain
  }

  // Check Ollama
  const ollamaHealthy = await isOllamaAvailable();
  const ollamaModels = await getAvailableModels();

  const status: HealthStatus = {
    db: dbHealthy,
    ollama: ollamaHealthy,
    ollamaModels,
    feedsCount,
    articlesCount,
    lastRefresh,
  };

  return NextResponse.json(status);
}
