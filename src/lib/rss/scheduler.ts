import type { Article } from "@/types";

const globalForScheduler = globalThis as unknown as {
  __newsixityScheduler: NodeJS.Timeout | undefined;
  __newsixitySchedulerStarted: boolean | undefined;
};

async function refreshAllFeeds(): Promise<void> {
  try {
    // Use dynamic imports to avoid circular dependency issues
    const { seedAllFeeds } = await import("@/lib/rss/feeds");
    const { fetchAllFeeds } = await import("@/lib/rss/parser");
    const { hashTitle } = await import("@/lib/dedup/similarity");
    const {
      upsertArticle,
      getArticleByTitleHash,
      getArticleById,
      getFeedCategorySlug,
    } =
      await import("@/lib/db/queries");
    const { groupArticles } = await import("@/lib/dedup/grouping");

    seedAllFeeds();
    const feedResults = await fetchAllFeeds();

    const newArticlesByCategory: Record<string, number[]> = {};

    for (const feedResult of feedResults) {
      if (feedResult.error) continue;

      // Get category slug for this feed
      const categorySlug = getFeedCategorySlug(feedResult.feedId);
      if (!categorySlug) continue;

      for (const article of feedResult.articles) {
        const titleHash = hashTitle(article.title);

        // Check exact title hash dedup
        const existing = getArticleByTitleHash(titleHash, categorySlug);
        if (existing) continue;

        const insertedId = upsertArticle(feedResult.feedId, article, titleHash);
        if (insertedId) {
          if (!newArticlesByCategory[categorySlug]) {
            newArticlesByCategory[categorySlug] = [];
          }
          newArticlesByCategory[categorySlug].push(insertedId);
        }
      }
    }

    // Group new articles by category
    for (const [slug, articleIds] of Object.entries(newArticlesByCategory)) {
      const articles = articleIds
        .map((id) => getArticleById(id))
        .filter((article): article is Article => article !== undefined);

      if (articles.length > 0) {
        groupArticles(articles, slug);
      }
    }

    console.log("[Newsixity] Feed refresh complete");

    // Score and promote articles for capped categories
    try {
      const { scoreAndPromoteAll } = await import("@/lib/ranking/promoter");
      scoreAndPromoteAll();
      console.log("[Newsixity] Article scoring and promotion complete");
    } catch (e) {
      console.warn("[Newsixity] Scoring/promotion error:", e);
    }

    // Background-summarize prioritized articles (saved > read > recent)
    try {
      const { backgroundSummarize } = await import("@/lib/ollama/background");
      backgroundSummarize(10).catch((e) =>
        console.warn("[Newsixity] Background summarization error:", e)
      );
    } catch {
      // Ollama module may not load — that's fine
    }
  } catch (error) {
    console.error("[Newsixity] Feed refresh error:", error);
  }
}

export function startScheduler(intervalMinutes: number = 15): void {
  if (globalForScheduler.__newsixitySchedulerStarted) return;
  globalForScheduler.__newsixitySchedulerStarted = true;

  console.log(
    `[Newsixity] Starting scheduler (interval: ${intervalMinutes}min)`
  );

  // Run initial refresh after a short delay (let the server start up)
  setTimeout(() => {
    refreshAllFeeds();
  }, 5000);

  // Set up periodic refresh
  globalForScheduler.__newsixityScheduler = setInterval(
    () => {
      refreshAllFeeds();
    },
    intervalMinutes * 60 * 1000
  );
}

export function stopScheduler(): void {
  if (globalForScheduler.__newsixityScheduler) {
    clearInterval(globalForScheduler.__newsixityScheduler);
    globalForScheduler.__newsixityScheduler = undefined;
    globalForScheduler.__newsixitySchedulerStarted = false;
    console.log("[Newsixity] Scheduler stopped");
  }
}
