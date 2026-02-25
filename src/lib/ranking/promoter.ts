import {
  CAPPED_CATEGORIES,
  DAILY_ARTICLE_LIMIT,
  getTodayArticleIds,
  promoteTopArticles,
} from "@/lib/db/queries";
import { scoreArticlesForCategory } from "./scorer";

/**
 * Run the full scoring + promotion pipeline for a category.
 * Scores all recent articles and marks the top N as promoted.
 * DELETION DISABLED: All articles are kept and visible.
 */
export function scoreAndPromote(
  categorySlug: string,
  limit: number = DAILY_ARTICLE_LIMIT
): void {
  // Get all articles from the last 24h in this category
  const articleIds = getTodayArticleIds(categorySlug);

  if (articleIds.length === 0) return;

  // Score them
  scoreArticlesForCategory(categorySlug, articleIds);

  // Promote the top N
  promoteTopArticles(categorySlug, limit);

  // DELETION DISABLED - keeping all articles visible
  // User wants to see all articles in all categories
  console.log(`[Newsixity] Scored and promoted top ${limit} articles in ${categorySlug}`);
}

/**
 * Run scoring + promotion for all capped categories.
 * Called after feed refresh completes.
 */
export function scoreAndPromoteAll(): void {
  for (const slug of CAPPED_CATEGORIES) {
    try {
      scoreAndPromote(slug);
    } catch (e) {
      console.warn(`[Newsixity] Scoring error for ${slug}:`, e);
    }
  }
}

/**
 * Check if a category has a daily article cap.
 */
export function isCappedCategory(slug: string): boolean {
  return CAPPED_CATEGORIES.includes(slug);
}
