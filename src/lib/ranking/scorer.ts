import type { Article } from "@/types";
import {
  getArticleGroupSize,
  getFeedSourceWeight,
  updateArticleScores,
  getArticleById,
} from "@/lib/db/queries";
import {
  getPreferencesForCategory,
  scorePreferenceMatch,
  type WeightedKeyword,
} from "./preferences";

// Title importance patterns — signals that an article is high-importance news
const IMPORTANCE_PATTERNS: { pattern: RegExp; bonus: number }[] = [
  { pattern: /\bbreaking\b/i, bonus: 1.0 },
  { pattern: /\bexclusive\b/i, bonus: 0.7 },
  { pattern: /\bjust in\b/i, bonus: 0.8 },
  { pattern: /\bdeveloping\b/i, bonus: 0.6 },
  { pattern: /\burgent\b/i, bonus: 0.8 },
  { pattern: /\bcrisis\b/i, bonus: 0.5 },
  { pattern: /\bdead\b|\bkilled\b|\bdeath toll\b/i, bonus: 0.4 },
  { pattern: /\belection\b|\bvote\b/i, bonus: 0.3 },
  { pattern: /\bwar\b|\binvasion\b|\battack\b/i, bonus: 0.4 },
  { pattern: /\brecord\b|\bhistoric\b|\bunprecedented\b/i, bonus: 0.3 },
  { pattern: /\bcrash\b|\bplunge\b|\bsurge\b|\bsoar\b/i, bonus: 0.3 },
  { pattern: /\bannounce\b|\blaunch\b|\breveal\b/i, bonus: 0.2 },
];

/**
 * Compute a title importance score (0 to 1) based on keyword signals.
 */
function computeTitleImportance(title: string): number {
  let score = 0;
  for (const { pattern, bonus } of IMPORTANCE_PATTERNS) {
    if (pattern.test(title)) {
      score += bonus;
    }
  }
  return Math.min(score, 1.0);
}

/**
 * Compute a recency score (0 to 1).
 * Full score within 6 hours, decays linearly to 0 over 24 hours.
 */
function computeRecencyScore(publishedAt: string | null): number {
  if (!publishedAt) return 0.3; // Unknown date gets a moderate score

  const publishedTime = new Date(publishedAt).getTime();
  const now = Date.now();
  const ageHours = (now - publishedTime) / (1000 * 60 * 60);

  if (ageHours < 0) return 1.0; // Future date (timezone quirks)
  if (ageHours <= 6) return 1.0;
  if (ageHours <= 24) return 1.0 - (ageHours - 6) / 18; // Linear decay 6h-24h
  return 0;
}

/**
 * Score a single article on a 0-100 scale using multiple signals:
 * - Group size (30%): more coverage = more important
 * - Preference match (30%): aligns with saved article patterns
 * - Source weight (20%): user-configurable feed reputation
 * - Recency (10%): newer is better
 * - Title importance (10%): breaking news keywords
 */
export function scoreArticle(
  article: Article,
  preferenceKeywords: WeightedKeyword[]
): number {
  const groupSize = getArticleGroupSize(article.id);
  const sourceWeight = getFeedSourceWeight(article.feedId);

  // Group score: 1 source = 0, 2 = 0.2, 3 = 0.4, 5+ = 1.0
  const groupScore = Math.min((groupSize - 1) / 4, 1.0) * 30;

  // Preference score
  const prefScore =
    scorePreferenceMatch(article.title, preferenceKeywords) * 30;

  // Source weight score: 0.5 = 0, 1.0 = 0.5, 2.0 = 1.0
  const sourceScore = (Math.min(Math.max(sourceWeight, 0.5), 2.0) - 0.5) / 1.5 * 20;

  // Recency score
  const recencyScore = computeRecencyScore(article.publishedAt) * 10;

  // Title importance score
  const importanceScore = computeTitleImportance(article.title) * 10;

  return Math.round(
    (groupScore + prefScore + sourceScore + recencyScore + importanceScore) * 10
  ) / 10;
}

/**
 * Score a batch of articles for a category and persist scores to DB.
 */
export function scoreArticlesForCategory(
  categorySlug: string,
  articleIds: number[]
): void {
  if (articleIds.length === 0) return;

  const keywords = getPreferencesForCategory(categorySlug);

  const updates: { id: number; score: number }[] = [];

  for (const id of articleIds) {
    const article = getArticleById(id);
    if (!article) continue;

    const score = scoreArticle(article, keywords);
    updates.push({ id, score });
  }

  if (updates.length > 0) {
    updateArticleScores(updates);
  }
}
