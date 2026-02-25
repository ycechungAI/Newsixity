import {
  getSavedArticles,
  getPreferenceKeywords,
  upsertPreferenceKeyword,
  clearAutoPreferences,
  type UserPreference,
} from "@/lib/db/queries";
import { CAPPED_CATEGORIES } from "@/lib/db/queries";

// English stop words to filter out when extracting keywords
const STOP_WORDS = new Set([
  "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
  "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
  "be", "have", "has", "had", "do", "does", "did", "will", "would",
  "could", "should", "may", "might", "shall", "can", "need", "dare",
  "ought", "used", "it", "its", "not", "no", "nor", "so", "too", "very",
  "just", "about", "above", "after", "again", "all", "also", "am", "any",
  "because", "before", "between", "both", "each", "few", "get", "got",
  "he", "her", "here", "him", "his", "how", "i", "if", "into", "me",
  "more", "most", "my", "new", "now", "off", "old", "only", "other",
  "our", "out", "over", "own", "re", "s", "same", "she", "some", "such",
  "t", "than", "that", "their", "them", "then", "there", "these", "they",
  "this", "those", "through", "under", "up", "us", "we", "what", "when",
  "where", "which", "while", "who", "whom", "why", "you", "your",
  "says", "said", "say", "report", "reports", "according", "first",
  "last", "make", "makes", "made", "take", "takes", "year", "years",
  "day", "days", "week", "weeks", "month", "months", "time", "people",
  "one", "two", "three", "way", "back", "even", "still", "after",
  "much", "many", "well", "set", "going", "being", "put",
]);

export interface WeightedKeyword {
  keyword: string;
  weight: number;
}

/**
 * Extract meaningful keywords from an article title.
 * Returns lowercased words with stop words removed.
 */
function extractKeywords(title: string): string[] {
  return title
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .split(/\s+/)
    .filter((w) => w.length > 2 && !STOP_WORDS.has(w));
}

/**
 * Rebuild the auto-generated preference keywords for a category
 * based on saved articles. Manual keywords are preserved.
 */
export function rebuildPreferences(categorySlug?: string): void {
  const categories = categorySlug ? [categorySlug] : CAPPED_CATEGORIES;

  for (const slug of categories) {
    // Get all saved articles in this category
    const saved = getSavedArticles({ limit: 500, categorySlug: slug });

    if (saved.length === 0) {
      clearAutoPreferences(slug);
      continue;
    }

    // Count keyword frequencies across saved articles
    const keywordCounts = new Map<string, number>();
    for (const article of saved) {
      const keywords = extractKeywords(article.title);
      const uniqueKeywords = new Set(keywords);
      for (const kw of uniqueKeywords) {
        keywordCounts.set(kw, (keywordCounts.get(kw) || 0) + 1);
      }
    }

    // Clear existing auto preferences for this category
    clearAutoPreferences(slug);

    // Normalize weights: most frequent keyword = 1.0
    const maxCount = Math.max(...keywordCounts.values(), 1);

    // Only keep keywords that appear in at least 2 saved articles
    // (or 1 if there are fewer than 3 saved articles total)
    const minOccurrences = saved.length < 3 ? 1 : 2;

    for (const [keyword, count] of keywordCounts) {
      if (count >= minOccurrences) {
        const weight = count / maxCount;
        upsertPreferenceKeyword(slug, keyword, weight, "auto");
      }
    }
  }
}

/**
 * Get weighted keyword list for a category.
 * Combines auto-generated and manual preferences.
 */
export function getPreferencesForCategory(
  categorySlug: string
): WeightedKeyword[] {
  const prefs = getPreferenceKeywords(categorySlug);
  return prefs.map((p: UserPreference) => ({
    keyword: p.keyword,
    weight: p.weight,
  }));
}

/**
 * Score how well an article title matches the user's preference keywords.
 * Returns a value between 0 and 1.
 */
export function scorePreferenceMatch(
  title: string,
  keywords: WeightedKeyword[]
): number {
  if (keywords.length === 0) return 0.5; // Neutral if no preferences yet

  const titleWords = new Set(extractKeywords(title));
  if (titleWords.size === 0) return 0;

  let matchScore = 0;
  let maxPossible = 0;

  for (const kw of keywords) {
    maxPossible += kw.weight;
    if (titleWords.has(kw.keyword)) {
      matchScore += kw.weight;
    }
  }

  if (maxPossible === 0) return 0.5;

  // Scale so even partial matches get meaningful scores
  // A single keyword match from the top preferences is significant
  return Math.min(matchScore / Math.min(maxPossible, 3), 1.0);
}

// Debounce tracking for preference rebuilds
let lastRebuildTime = 0;
const REBUILD_DEBOUNCE_MS = 5 * 60 * 1000; // 5 minutes

/**
 * Trigger a debounced preference rebuild. Won't run more than
 * once every 5 minutes to avoid thrashing during batch operations.
 */
export function triggerPreferenceRebuild(categorySlug?: string): void {
  const now = Date.now();
  if (now - lastRebuildTime < REBUILD_DEBOUNCE_MS) return;
  lastRebuildTime = now;
  rebuildPreferences(categorySlug);
}
