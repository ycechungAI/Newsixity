import { summarizeArticle, isOllamaAvailable } from "./client";
import {
  getUnsummarizedSavedArticles,
  getUnsummarizedByCategory,
  getRecentUnsummarizedArticles,
  getSummarizeCategoryPriority,
  updateArticleSummary,
  updateArticleContent,
  getArticleById,
} from "@/lib/db/queries";
import { fetchArticleContent } from "@/lib/content/fetcher";
import type { Article } from "@/types";
import { OllamaUnavailableError } from "@/types";

const DEFAULT_MODEL = "llama3.2";
const BATCH_SIZE = 30;

/**
 * Track whether a background batch is already running so we don't pile up.
 */
let backgroundRunning = false;

/**
 * Summarize a single article, returning true on success.
 * If content is missing, attempts to fetch it from the original URL first.
 */
async function summarizeOne(article: Article): Promise<boolean> {
  let content = article.content;

  // If no content from RSS, try fetching from original URL
  if ((!content || content.length <= 10) && article.link) {
    console.log(
      `[Newsixity] No RSS content for article ${article.id}, fetching from ${article.link}`
    );
    const fetched = await fetchArticleContent(article.link);
    if (fetched && fetched.length > 50) {
      content = fetched;
      updateArticleContent(article.id, fetched);
    }
  }

  if (!content || content.length <= 10) return false;

  const summary = await summarizeArticle(article.title, content);
  updateArticleSummary(article.id, summary, DEFAULT_MODEL);

  console.log(
    `[Newsixity] Summarized article ${article.id}: "${article.title.slice(0, 50)}..."`
  );
  return true;
}

/**
 * Process a batch of articles. Returns count summarized.
 * Throws OllamaUnavailableError if Ollama goes offline (caller should stop).
 */
async function processBatch(
  articles: Article[],
  label: string,
  errors: string[]
): Promise<number> {
  if (articles.length === 0) return 0;

  console.log(
    `[Newsixity] Summarizing batch [${label}]: ${articles.length} articles`
  );

  let count = 0;
  for (const article of articles) {
    // Check for newly saved articles between each article — they jump the queue
    const urgent = getUnsummarizedSavedArticles(1);
    if (urgent.length > 0 && label !== "saved") {
      // There's a new saved article — process it immediately
      try {
        if (await summarizeOne(urgent[0])) count++;
      } catch (e) {
        if (e instanceof OllamaUnavailableError) throw e;
        errors.push(`Article ${urgent[0].id}: ${e instanceof Error ? e.message : String(e)}`);
      }
    }

    try {
      if (await summarizeOne(article)) count++;
    } catch (e) {
      if (e instanceof OllamaUnavailableError) throw e;
      errors.push(`Article ${article.id}: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  return count;
}

/**
 * Summarize articles in priority order:
 *
 *   1. Saved articles (always top priority, checked between batches)
 *   2. Recently fetched articles (newer than 20min — fresh content)
 *   3. Category batches in priority order:
 *      Top News → Technology → Finance → World News → Gaming → Sports
 *   4. Each category processes 30 at a time, then moves to the next
 *   5. After all categories do their first 30, loops back for remaining
 *
 * Stops early if Ollama goes offline.
 */
export async function backgroundSummarize(limit: number = 10): Promise<{
  summarized: number;
  errors: string[];
}> {
  if (backgroundRunning) {
    return { summarized: 0, errors: ["Background summarization already in progress"] };
  }

  backgroundRunning = true;
  let summarized = 0;
  const errors: string[] = [];

  try {
    const available = await isOllamaAvailable();
    if (!available) {
      return { summarized: 0, errors: ["Ollama is not available"] };
    }

    // --- Priority 1: Saved articles ---
    const saved = getUnsummarizedSavedArticles(BATCH_SIZE);
    if (saved.length > 0) {
      summarized += await processBatch(saved, "saved", errors);
    }

    // --- Priority 2: Recently fetched (new articles from latest refresh) ---
    const recent = getRecentUnsummarizedArticles(20, BATCH_SIZE);
    if (recent.length > 0) {
      // Filter out any we already summarized as saved
      const recentFiltered = recent.filter(
        (a) => !saved.some((s) => s.id === a.id)
      );
      if (recentFiltered.length > 0) {
        // Check for new saved articles first
        const urgentSaved = getUnsummarizedSavedArticles(BATCH_SIZE);
        if (urgentSaved.length > 0) {
          summarized += await processBatch(urgentSaved, "saved (urgent)", errors);
        }
        summarized += await processBatch(recentFiltered, "recent", errors);
      }
    }

    // --- Priority 3: Category batches in priority order ---
    const categoryPriority = getSummarizeCategoryPriority();
    let moreWork = true;

    while (moreWork) {
      moreWork = false;

      // Check for saved articles before each round
      const urgentSaved = getUnsummarizedSavedArticles(BATCH_SIZE);
      if (urgentSaved.length > 0) {
        summarized += await processBatch(urgentSaved, "saved (between rounds)", errors);
      }

      // Check for recently fetched articles (new refresh may have happened)
      const freshRecent = getRecentUnsummarizedArticles(20, BATCH_SIZE);
      if (freshRecent.length > 0) {
        summarized += await processBatch(freshRecent, "recent (between rounds)", errors);
      }

      for (const slug of categoryPriority) {
        const batch = getUnsummarizedByCategory(slug, BATCH_SIZE);
        if (batch.length === 0) continue;

        moreWork = true;
        summarized += await processBatch(batch, slug, errors);

        // After each category batch, check for saved articles again
        const midSaved = getUnsummarizedSavedArticles(BATCH_SIZE);
        if (midSaved.length > 0) {
          summarized += await processBatch(midSaved, "saved (mid-round)", errors);
        }
      }
    }

    console.log(
      `[Newsixity] Background summarize done: ${summarized} summarized, ${errors.length} errors`
    );
  } catch (e) {
    if (e instanceof OllamaUnavailableError) {
      console.warn("[Newsixity] Ollama went offline, stopping background batch");
      errors.push("Ollama became unavailable");
    } else {
      const message = e instanceof Error ? e.message : String(e);
      errors.push(message);
    }
  } finally {
    backgroundRunning = false;
  }

  return { summarized, errors };
}

/**
 * Summarize a single article by ID (fire-and-forget).
 * Used when a user saves an article to immediately queue it.
 */
export async function summarizeArticleById(articleId: number): Promise<void> {
  try {
    const article = getArticleById(articleId);
    if (!article) return;

    // Already has a summary
    if (article.summary) return;

    // No content to summarize
    if (!article.content || article.content.length <= 10) return;

    const available = await isOllamaAvailable();
    if (!available) return;

    const summary = await summarizeArticle(article.title, article.content);
    updateArticleSummary(articleId, summary, DEFAULT_MODEL);

    console.log(
      `[Newsixity] On-demand summarized article ${articleId}: "${article.title.slice(0, 50)}..."`
    );
  } catch (e) {
    // Fire-and-forget — just log
    const message = e instanceof Error ? e.message : String(e);
    console.warn(`[Newsixity] Failed to summarize article ${articleId}: ${message}`);
  }
}
