import { createHash } from "crypto";
import { getDb } from "./index";
import type {
  Category,
  Feed,
  Article,
  ArticleGroup,
  ParsedArticle,
  ArticleResearch,
  ResearchSource,
} from "@/types";
import type {
  WatchlistItem,
  StockQuote,
  CachedQuote,
  CachedChart,
  ChartDataPoint,
} from "@/lib/finance/types";

// ---------------------------------------------------------------------------
// Helper: map a raw DB row (snake_case) to an Article (camelCase)
// ---------------------------------------------------------------------------
function mapArticleRow(row: any): Article {
  return {
    id: row.id,
    feedId: row.feed_id,
    feedName: row.feed_name ?? "",
    categorySlug: row.category_slug ?? "",
    guid: row.guid,
    title: row.title,
    link: row.link,
    author: row.author ?? null,
    publishedAt: row.published_at ?? null,
    content: row.content ?? null,
    imageUrl: row.image_url ?? null,
    summary: row.summary ?? null,
    summaryModel: row.summary_model ?? null,
    isRead: row.is_read === 1,
    isSaved: row.is_saved === 1,
    groupId: row.group_id ?? null,
    fetchedAt: row.fetched_at,
  };
}

const ARTICLE_SELECT = `
  SELECT a.*, f.name AS feed_name, c.slug AS category_slug
  FROM articles a
  JOIN feeds f ON a.feed_id = f.id
  JOIN categories c ON f.category_id = c.id
`;

// ---------------------------------------------------------------------------
// Categories
// ---------------------------------------------------------------------------
export function getCategories(): Category[] {
  const db = getDb();
  const rows = db
    .prepare("SELECT * FROM categories ORDER BY sort_order")
    .all() as any[];
  return rows.map((r) => ({
    id: r.id,
    name: r.name,
    slug: r.slug,
    sortOrder: r.sort_order,
  }));
}

export function getCategoryBySlug(slug: string): Category | undefined {
  const db = getDb();
  const row = db
    .prepare("SELECT * FROM categories WHERE slug = ?")
    .get(slug) as any | undefined;
  if (!row) return undefined;
  return {
    id: row.id,
    name: row.name,
    slug: row.slug,
    sortOrder: row.sort_order,
  };
}

// ---------------------------------------------------------------------------
// Articles
// ---------------------------------------------------------------------------
export function getArticlesByCategory(
  slug: string | null,
  options: { limit?: number; offset?: number; unreadOnly?: boolean } = {}
): Article[] {
  const db = getDb();
  const { limit = 50, offset = 0, unreadOnly = false } = options;

  const conditions: string[] = [];
  const params: any[] = [];

  if (slug) {
    conditions.push("c.slug = ?");
    params.push(slug);
  }
  if (unreadOnly) {
    conditions.push("a.is_read = 0");
  }

  const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";

  const sql = `
    ${ARTICLE_SELECT}
    ${where}
    ORDER BY a.is_read ASC, a.published_at DESC
    LIMIT ? OFFSET ?
  `;
  params.push(limit, offset);

  const rows = db.prepare(sql).all(...params) as any[];
  return rows.map(mapArticleRow);
}

export function getArticleGroupsByCategory(
  slug: string | null,
  limit: number = 30
): ArticleGroup[] {
  const db = getDb();

  const conditions: string[] = [];
  const params: any[] = [];

  if (slug) {
    conditions.push("c.slug = ?");
    params.push(slug);
  }

  const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";

  const groupsSql = `
    SELECT ag.*,
      (SELECT COUNT(*) FROM articles a2 WHERE a2.group_id = ag.id AND a2.is_read = 0) AS unread_count
    FROM article_groups ag
    JOIN categories c ON ag.category_id = c.id
    ${where}
    ORDER BY (unread_count > 0) DESC, ag.updated_at DESC
    LIMIT ?
  `;
  params.push(limit);

  const groupRows = db.prepare(groupsSql).all(...params) as any[];

  return groupRows.map((g) => {
    // Get all articles in this group
    const articleRows = db
      .prepare(`${ARTICLE_SELECT} WHERE a.group_id = ? ORDER BY a.is_read ASC, a.published_at DESC`)
      .all(g.id) as any[];
    const articles = articleRows.map(mapArticleRow);

    // Find the representative article
    const repRow = g.representative_id
      ? (db
          .prepare(`${ARTICLE_SELECT} WHERE a.id = ?`)
          .get(g.representative_id) as any | undefined)
      : null;
    const representative = repRow ? mapArticleRow(repRow) : articles[0];

    return {
      id: g.id,
      label: g.label,
      categoryId: g.category_id,
      representativeId: g.representative_id,
      articleCount: g.article_count,
      representative,
      articles,
    } as ArticleGroup;
  });
}

export function getArticleById(id: number): Article | undefined {
  const db = getDb();
  const row = db
    .prepare(`${ARTICLE_SELECT} WHERE a.id = ?`)
    .get(id) as any | undefined;
  if (!row) return undefined;
  return mapArticleRow(row);
}

export function upsertArticle(
  feedId: number,
  article: ParsedArticle,
  titleHash: string
): number | null {
  const db = getDb();
  const result = db
    .prepare(
      `INSERT OR IGNORE INTO articles
        (feed_id, guid, title, link, author, published_at, content, image_url, title_hash)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
    )
    .run(
      feedId,
      article.guid,
      article.title,
      article.link,
      article.author,
      article.publishedAt,
      article.content,
      article.imageUrl,
      titleHash
    );

  if (result.changes === 0) return null;
  return result.lastInsertRowid as number;
}

export function updateArticleSummary(
  id: number,
  summary: string,
  model: string
): void {
  const db = getDb();
  db.prepare(
    "UPDATE articles SET summary = ?, summary_model = ? WHERE id = ?"
  ).run(summary, model, id);
}

export function updateArticleContent(id: number, content: string): void {
  const db = getDb();
  db.prepare("UPDATE articles SET content = ? WHERE id = ?").run(content, id);
}

export function markArticleRead(id: number): void {
  const db = getDb();
  db.prepare("UPDATE articles SET is_read = 1 WHERE id = ?").run(id);
}

export function markArticleUnread(id: number): void {
  const db = getDb();
  db.prepare("UPDATE articles SET is_read = 0 WHERE id = ?").run(id);
}

export function markAllReadByCategory(slug: string | null): number {
  const db = getDb();
  if (slug) {
    const result = db
      .prepare(
        `UPDATE articles SET is_read = 1
         WHERE is_read = 0 AND feed_id IN (
           SELECT f.id FROM feeds f JOIN categories c ON f.category_id = c.id WHERE c.slug = ?
         )`
      )
      .run(slug);
    return result.changes;
  }
  const result = db
    .prepare("UPDATE articles SET is_read = 1 WHERE is_read = 0")
    .run();
  return result.changes;
}

export function toggleArticleSaved(id: number): void {
  const db = getDb();
  db.prepare(
    "UPDATE articles SET is_saved = CASE WHEN is_saved = 1 THEN 0 ELSE 1 END WHERE id = ?"
  ).run(id);
}

export function getSavedArticles(
  options: { limit?: number; offset?: number; categorySlug?: string } = {}
): Article[] {
  const db = getDb();
  const { limit = 50, offset = 0, categorySlug } = options;

  let query = `${ARTICLE_SELECT} WHERE a.is_saved = 1`;
  const params: any[] = [];

  if (categorySlug) {
    query += " AND c.slug = ?";
    params.push(categorySlug);
  }

  query += " ORDER BY a.published_at DESC LIMIT ? OFFSET ?";
  params.push(limit, offset);

  const rows = db.prepare(query).all(...params) as any[];
  return rows.map(mapArticleRow);
}

export function getSavedArticleCount(categorySlug?: string): number {
  const db = getDb();

  let query = "SELECT COUNT(*) AS count FROM articles a";
  const params: any[] = [];

  if (categorySlug) {
    query += " JOIN feeds f ON a.feed_id = f.id JOIN categories c ON f.category_id = c.id";
    query += " WHERE a.is_saved = 1 AND c.slug = ?";
    params.push(categorySlug);
  } else {
    query += " WHERE a.is_saved = 1";
  }

  const row = db.prepare(query).get(...params) as any;
  return row?.count ?? 0;
}

export function getUnsummarizedArticles(
  limit: number,
  categorySlug?: string
): Article[] {
  const db = getDb();

  const conditions = ["a.summary IS NULL"];
  const params: any[] = [];

  if (categorySlug) {
    conditions.push("c.slug = ?");
    params.push(categorySlug);
  }

  const where = `WHERE ${conditions.join(" AND ")}`;
  params.push(limit);

  const rows = db
    .prepare(
      `${ARTICLE_SELECT}
       ${where}
       ORDER BY a.published_at DESC
       LIMIT ?`
    )
    .all(...params) as any[];
  return rows.map(mapArticleRow);
}

/**
 * Get unsummarized articles prioritized for background generation:
 * 1. Saved articles first (user explicitly bookmarked)
 * 2. Read/viewed articles next (user showed interest)
 * 3. Recent articles last
 * Only includes articles with enough content to summarize (>50 chars).
 */
/**
 * Category priority for AI summarization.
 * Lower index = higher priority.
 */
const SUMMARIZE_CATEGORY_PRIORITY = [
  "top-news",
  "technology",
  "finance",
  "world-news",
  "gaming",
  "sports",
];

/**
 * Get unsummarized saved articles (highest priority).
 * Includes articles with no content — fetcher will retrieve from URL.
 */
export function getUnsummarizedSavedArticles(limit: number = 30): Article[] {
  const db = getDb();
  const rows = db
    .prepare(
      `${ARTICLE_SELECT}
       WHERE a.summary IS NULL
         AND a.is_saved = 1
         AND (a.link IS NOT NULL AND a.link != '')
       ORDER BY a.published_at DESC
       LIMIT ?`
    )
    .all(limit) as any[];
  return rows.map(mapArticleRow);
}

/**
 * Get unsummarized articles for a specific category.
 * Includes articles with no content — fetcher will retrieve from URL.
 */
export function getUnsummarizedByCategory(
  categorySlug: string,
  limit: number = 30
): Article[] {
  const db = getDb();
  const rows = db
    .prepare(
      `${ARTICLE_SELECT}
       WHERE a.summary IS NULL
         AND a.is_saved = 0
         AND c.slug = ?
         AND (a.link IS NOT NULL AND a.link != '')
       ORDER BY a.published_at DESC
       LIMIT ?`
    )
    .all(categorySlug, limit) as any[];
  return rows.map(mapArticleRow);
}

/**
 * Get recently fetched unsummarized articles (newer than given timestamp).
 * Includes articles with no content — fetcher will retrieve from URL.
 */
export function getRecentUnsummarizedArticles(
  sinceMinutes: number = 20,
  limit: number = 30
): Article[] {
  const db = getDb();
  const rows = db
    .prepare(
      `${ARTICLE_SELECT}
       WHERE a.summary IS NULL
         AND a.fetched_at > datetime('now', '-' || ? || ' minutes')
         AND (a.link IS NOT NULL AND a.link != '')
       ORDER BY a.is_saved DESC, a.published_at DESC
       LIMIT ?`
    )
    .all(sinceMinutes, limit) as any[];
  return rows.map(mapArticleRow);
}

/**
 * Get the category priority order for summarization.
 */
export function getSummarizeCategoryPriority(): string[] {
  return [...SUMMARIZE_CATEGORY_PRIORITY];
}

/**
 * Legacy function kept for compatibility.
 * Returns saved first, then by category priority.
 */
export function getUnsummarizedArticlesPrioritized(
  limit: number = 20
): Article[] {
  const db = getDb();

  // Build a CASE expression for category priority
  const caseParts = SUMMARIZE_CATEGORY_PRIORITY.map(
    (slug, i) => `WHEN '${slug}' THEN ${i + 1}`
  ).join(" ");
  const categoryOrder = `CASE c.slug ${caseParts} ELSE 99 END`;

  const rows = db
    .prepare(
      `${ARTICLE_SELECT}
       WHERE a.summary IS NULL
         AND a.content IS NOT NULL
         AND LENGTH(a.content) > 50
       ORDER BY
         a.is_saved DESC,
         ${categoryOrder},
         a.published_at DESC
       LIMIT ?`
    )
    .all(limit) as any[];
  return rows.map(mapArticleRow);
}

export function searchArticles(
  query: string,
  options: { category?: string; limit?: number } = {}
): Article[] {
  const db = getDb();
  const { category, limit = 50 } = options;

  const conditions = ["a.title LIKE ?"];
  const params: any[] = [`%${query}%`];

  if (category) {
    conditions.push("c.slug = ?");
    params.push(category);
  }

  const where = `WHERE ${conditions.join(" AND ")}`;
  params.push(limit);

  const rows = db
    .prepare(
      `${ARTICLE_SELECT}
       ${where}
       ORDER BY a.published_at DESC
       LIMIT ?`
    )
    .all(...params) as any[];
  return rows.map(mapArticleRow);
}

export function getArticleByTitleHash(
  titleHash: string,
  categorySlug: string
): Article | undefined {
  const db = getDb();
  const row = db
    .prepare(
      `${ARTICLE_SELECT}
       WHERE a.title_hash = ?
         AND c.slug = ?
         AND a.published_at >= datetime('now', '-48 hours')
       LIMIT 1`
    )
    .get(titleHash, categorySlug) as any | undefined;
  if (!row) return undefined;
  return mapArticleRow(row);
}

// ---------------------------------------------------------------------------
// Feeds
// ---------------------------------------------------------------------------
export function getAllFeeds(): Feed[] {
  const db = getDb();
  const rows = db
    .prepare(
      `SELECT f.*, c.slug AS category_slug
       FROM feeds f
       JOIN categories c ON f.category_id = c.id
       ORDER BY c.sort_order, f.name`
    )
    .all() as any[];
  return rows.map((r) => ({
    id: r.id,
    categoryId: r.category_id,
    name: r.name,
    url: r.url,
    enabled: r.enabled === 1,
    lastFetchedAt: r.last_fetched_at ?? null,
    lastError: r.last_error ?? null,
  }));
}

export function getFeedsByCategory(categorySlug: string): Feed[] {
  const db = getDb();
  const rows = db
    .prepare(
      `SELECT f.*
       FROM feeds f
       JOIN categories c ON f.category_id = c.id
       WHERE c.slug = ?
       ORDER BY f.name`
    )
    .all(categorySlug) as any[];
  return rows.map((r) => ({
    id: r.id,
    categoryId: r.category_id,
    name: r.name,
    url: r.url,
    enabled: r.enabled === 1,
    lastFetchedAt: r.last_fetched_at ?? null,
    lastError: r.last_error ?? null,
  }));
}

export function updateFeedLastFetched(feedId: number, error?: string): void {
  const db = getDb();
  db.prepare(
    `UPDATE feeds SET last_fetched_at = datetime('now'), last_error = ? WHERE id = ?`
  ).run(error ?? null, feedId);
}

// ---------------------------------------------------------------------------
// Article Groups
// ---------------------------------------------------------------------------
export function assignArticleToGroup(
  articleId: number,
  groupId: number
): void {
  const db = getDb();
  db.prepare("UPDATE articles SET group_id = ? WHERE id = ?").run(
    groupId,
    articleId
  );
}

export function createGroup(
  label: string | null,
  categoryId: number,
  representativeId: number
): number {
  const db = getDb();
  const result = db
    .prepare(
      `INSERT INTO article_groups (label, category_id, representative_id)
       VALUES (?, ?, ?)`
    )
    .run(label, categoryId, representativeId);
  return result.lastInsertRowid as number;
}

export function updateGroupRepresentative(
  groupId: number,
  representativeId: number
): void {
  const db = getDb();
  db.prepare(
    `UPDATE article_groups
     SET representative_id = ?, updated_at = datetime('now')
     WHERE id = ?`
  ).run(representativeId, groupId);
}

export function incrementGroupCount(groupId: number): void {
  const db = getDb();
  db.prepare(
    `UPDATE article_groups
     SET article_count = article_count + 1, updated_at = datetime('now')
     WHERE id = ?`
  ).run(groupId);
}

export function getRecentGroupsByCategory(
  categorySlug: string,
  hours: number = 48
): { id: number; label: string | null; representativeTitle: string; categoryId: number }[] {
  const db = getDb();
  const rows = db
    .prepare(
      `SELECT ag.id, ag.label, ag.category_id, a.title AS representative_title
       FROM article_groups ag
       JOIN categories c ON ag.category_id = c.id
       LEFT JOIN articles a ON ag.representative_id = a.id
       WHERE c.slug = ?
         AND ag.updated_at >= datetime('now', '-' || ? || ' hours')
       ORDER BY ag.updated_at DESC`
    )
    .all(categorySlug, hours) as any[];
  return rows.map((r) => ({
    id: r.id,
    label: r.label,
    representativeTitle: r.representative_title,
    categoryId: r.category_id,
  }));
}

// ---------------------------------------------------------------------------
// Stats & Seeding
// ---------------------------------------------------------------------------
export function getArticleCountByCategory(): {
  slug: string;
  total: number;
  unread: number;
}[] {
  const db = getDb();
  const rows = db
    .prepare(
      `SELECT
         c.slug,
         COUNT(a.id) AS total,
         SUM(CASE WHEN a.is_read = 0 THEN 1 ELSE 0 END) AS unread
       FROM categories c
       LEFT JOIN feeds f ON f.category_id = c.id
       LEFT JOIN articles a ON a.feed_id = f.id
       GROUP BY c.slug
       ORDER BY c.sort_order`
    )
    .all() as any[];
  return rows.map((r) => ({
    slug: r.slug,
    total: r.total ?? 0,
    unread: r.unread ?? 0,
  }));
}

export function seedFeed(
  categorySlug: string,
  name: string,
  url: string
): void {
  const db = getDb();
  const category = db
    .prepare("SELECT id FROM categories WHERE slug = ?")
    .get(categorySlug) as { id: number } | undefined;
  if (!category) {
    throw new Error(`Category "${categorySlug}" not found`);
  }
  db.prepare(
    "INSERT OR IGNORE INTO feeds (category_id, name, url) VALUES (?, ?, ?)"
  ).run(category.id, name, url);
}

// ---------------------------------------------------------------------------
// Article Research (Deep Research cache)
// ---------------------------------------------------------------------------
export function getArticleResearch(
  articleId: number,
  question: string
): ArticleResearch | undefined {
  const db = getDb();
  const row = db
    .prepare(
      `SELECT * FROM article_research
       WHERE article_id = ? AND question = ?
       ORDER BY created_at DESC
       LIMIT 1`
    )
    .get(articleId, question) as any | undefined;
  if (!row) return undefined;
  return {
    id: row.id,
    articleId: row.article_id,
    question: row.question,
    answer: row.answer,
    sources: JSON.parse(row.sources || "[]"),
    model: row.model,
    createdAt: row.created_at,
  };
}

export function saveArticleResearch(
  articleId: number,
  question: string,
  answer: string,
  sources: ResearchSource[],
  model: string
): number {
  const db = getDb();
  const result = db
    .prepare(
      `INSERT INTO article_research (article_id, question, answer, sources, model)
       VALUES (?, ?, ?, ?, ?)`
    )
    .run(articleId, question, answer, JSON.stringify(sources), model);
  return result.lastInsertRowid as number;
}

export function getAllArticleResearch(articleId: number): ArticleResearch[] {
  const db = getDb();
  const rows = db
    .prepare(
      `SELECT * FROM article_research
       WHERE article_id = ?
       ORDER BY created_at DESC`
    )
    .all(articleId) as any[];
  return rows.map((row) => ({
    id: row.id,
    articleId: row.article_id,
    question: row.question,
    answer: row.answer,
    sources: JSON.parse(row.sources || "[]"),
    model: row.model,
    createdAt: row.created_at,
  }));
}

export function deleteArticleResearch(researchId: number): void {
  const db = getDb();
  db.prepare("DELETE FROM article_research WHERE id = ?").run(researchId);
}

// ---------------------------------------------------------------------------
// Search Quota Management
// ---------------------------------------------------------------------------
const MONTHLY_QUOTA_LIMIT = 1900;

function getCurrentMonthKey(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  return `${year}-${month}`;
}

export interface SearchQuota {
  id: number;
  monthKey: string;
  queryCount: number;
  createdAt: string;
  updatedAt: string;
}

export function getMonthlyQuota(): SearchQuota {
  const db = getDb();
  const monthKey = getCurrentMonthKey();

  // Get or create quota record for current month
  let row = db
    .prepare("SELECT * FROM search_quota WHERE month_key = ?")
    .get(monthKey) as any | undefined;

  if (!row) {
    // Create new quota record for this month
    db.prepare(
      "INSERT INTO search_quota (month_key, query_count) VALUES (?, 0)"
    ).run(monthKey);

    row = db
      .prepare("SELECT * FROM search_quota WHERE month_key = ?")
      .get(monthKey) as any;
  }

  return {
    id: row.id,
    monthKey: row.month_key,
    queryCount: row.query_count,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

export function incrementQuota(): number {
  const db = getDb();
  const monthKey = getCurrentMonthKey();

  // Ensure quota record exists
  getMonthlyQuota();

  // Increment the counter
  db.prepare(
    `UPDATE search_quota
     SET query_count = query_count + 1,
         updated_at = datetime('now')
     WHERE month_key = ?`
  ).run(monthKey);

  // Return new count
  const quota = getMonthlyQuota();
  return quota.queryCount;
}

export function isQuotaExceeded(): boolean {
  const quota = getMonthlyQuota();
  return quota.queryCount >= MONTHLY_QUOTA_LIMIT;
}

export function getRemainingQuota(): number {
  const quota = getMonthlyQuota();
  return Math.max(0, MONTHLY_QUOTA_LIMIT - quota.queryCount);
}

// ---------------------------------------------------------------------------
// Settings Management
// ---------------------------------------------------------------------------
export function getSetting(key: string): string | null {
  const db = getDb();
  const row = db
    .prepare("SELECT value FROM settings WHERE key = ?")
    .get(key) as { value: string | null } | undefined;
  return row?.value ?? null;
}

export function setSetting(key: string, value: string | null): void {
  const db = getDb();
  db.prepare(
    `INSERT INTO settings (key, value, updated_at)
     VALUES (?, ?, datetime('now'))
     ON CONFLICT(key) DO UPDATE SET
       value = excluded.value,
       updated_at = datetime('now')`
  ).run(key, value);
}

export function getAllSettings(): Record<string, string | null> {
  const db = getDb();
  const rows = db
    .prepare("SELECT key, value FROM settings")
    .all() as { key: string; value: string | null }[];

  const settings: Record<string, string | null> = {};
  for (const row of rows) {
    settings[row.key] = row.value;
  }
  return settings;
}

export function deleteSetting(key: string): void {
  const db = getDb();
  db.prepare("DELETE FROM settings WHERE key = ?").run(key);
}

// ---------------------------------------------------------------------------
// Finance: Watchlist
// ---------------------------------------------------------------------------

export function getWatchlist(): WatchlistItem[] {
  const db = getDb();
  const rows = db
    .prepare(
      `SELECT id, symbol, name, exchange, added_at as addedAt
       FROM stock_watchlist
       ORDER BY added_at DESC`
    )
    .all() as WatchlistItem[];
  return rows;
}

export function addToWatchlist(symbol: string, name: string, exchange: string): number {
  const db = getDb();
  const result = db
    .prepare(
      `INSERT INTO stock_watchlist (symbol, name, exchange)
       VALUES (?, ?, ?)`
    )
    .run(symbol, name, exchange);
  return result.lastInsertRowid as number;
}

export function removeFromWatchlist(id: number): void {
  const db = getDb();
  db.prepare("DELETE FROM stock_watchlist WHERE id = ?").run(id);
}

export function isInWatchlist(symbol: string): boolean {
  const db = getDb();
  const row = db
    .prepare("SELECT id FROM stock_watchlist WHERE symbol = ?")
    .get(symbol);
  return !!row;
}

// ---------------------------------------------------------------------------
// Finance: Quote Cache
// ---------------------------------------------------------------------------

export function getCachedQuote(symbol: string): StockQuote | null {
  const db = getDb();
  const row = db
    .prepare(
      `SELECT symbol, price, change, change_percent as changePercent,
              volume, market_cap as marketCap, currency, expires_at as expiresAt
       FROM stock_quotes_cache
       WHERE symbol = ? AND datetime(expires_at) > datetime('now')`
    )
    .get(symbol) as CachedQuote | undefined;

  if (!row) return null;

  return {
    symbol: row.symbol,
    name: '', // Not stored in cache, will be filled from watchlist
    exchange: '', // Not stored in cache
    price: row.price,
    change: row.change,
    changePercent: row.changePercent,
    volume: row.volume,
    marketCap: row.marketCap,
    currency: row.currency || 'USD',
    fiftyTwoWeekHigh: null,
    fiftyTwoWeekLow: null,
    marketState: 'CLOSED',
  };
}

export function setCachedQuote(quote: StockQuote, ttlMinutes: number): void {
  const db = getDb();
  const expiresAt = new Date(Date.now() + ttlMinutes * 60 * 1000).toISOString();

  db.prepare(
    `INSERT INTO stock_quotes_cache
      (symbol, price, change, change_percent, volume, market_cap, currency, expires_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(symbol) DO UPDATE SET
       price = excluded.price,
       change = excluded.change,
       change_percent = excluded.change_percent,
       volume = excluded.volume,
       market_cap = excluded.market_cap,
       currency = excluded.currency,
       cached_at = datetime('now'),
       expires_at = excluded.expires_at`
  ).run(
    quote.symbol,
    quote.price,
    quote.change,
    quote.changePercent,
    quote.volume,
    quote.marketCap,
    quote.currency,
    expiresAt
  );
}

export function getCachedQuotes(symbols: string[]): Map<string, StockQuote> {
  const quotes = new Map<string, StockQuote>();
  for (const symbol of symbols) {
    const quote = getCachedQuote(symbol);
    if (quote) {
      quotes.set(symbol, quote);
    }
  }
  return quotes;
}

// ---------------------------------------------------------------------------
// Finance: Chart Cache
// ---------------------------------------------------------------------------

export function getCachedChart(symbol: string, timeframe: string): { data: ChartDataPoint[]; cached: boolean } | null {
  const db = getDb();
  const row = db
    .prepare(
      `SELECT data
       FROM stock_charts_cache
       WHERE symbol = ? AND timeframe = ? AND datetime(expires_at) > datetime('now')`
    )
    .get(symbol, timeframe) as { data: string } | undefined;

  if (!row) return null;

  try {
    const data = JSON.parse(row.data) as ChartDataPoint[];
    return { data, cached: true };
  } catch {
    return null;
  }
}

export function setCachedChart(
  symbol: string,
  timeframe: string,
  data: ChartDataPoint[],
  ttlHours: number
): void {
  const db = getDb();
  const expiresAt = new Date(Date.now() + ttlHours * 60 * 60 * 1000).toISOString();
  const dataJson = JSON.stringify(data);

  db.prepare(
    `INSERT INTO stock_charts_cache (symbol, timeframe, data, expires_at)
     VALUES (?, ?, ?, ?)
     ON CONFLICT(symbol, timeframe) DO UPDATE SET
       data = excluded.data,
       cached_at = datetime('now'),
       expires_at = excluded.expires_at`
  ).run(symbol, timeframe, dataJson, expiresAt);
}

// ---------------------------------------------------------------------------
// Finance: Cache Cleanup
// ---------------------------------------------------------------------------

export function cleanExpiredQuotes(): number {
  const db = getDb();
  const result = db
    .prepare("DELETE FROM stock_quotes_cache WHERE datetime(expires_at) <= datetime('now')")
    .run();
  return result.changes;
}

export function cleanExpiredCharts(): number {
  const db = getDb();
  const result = db
    .prepare("DELETE FROM stock_charts_cache WHERE datetime(expires_at) <= datetime('now')")
    .run();
  return result.changes;
}

// ---------------------------------------------------------------------------
// Finance: Market Heatmap Snapshots
// ---------------------------------------------------------------------------

export interface HeatmapSnapshot {
  id: number;
  date: string;
  data: string;
  createdAt: string;
}

export function getHeatmapSnapshot(date: string): HeatmapSnapshot | null {
  const db = getDb();
  const row = db
    .prepare('SELECT id, date, data, created_at as createdAt FROM market_heatmap_snapshots WHERE date = ?')
    .get(date) as HeatmapSnapshot | undefined;
  return row || null;
}

export function saveHeatmapSnapshot(date: string, data: string): number {
  const db = getDb();
  const result = db
    .prepare(`
      INSERT INTO market_heatmap_snapshots (date, data)
      VALUES (?, ?)
      ON CONFLICT(date) DO UPDATE SET data = ?, created_at = datetime('now')
    `)
    .run(date, data, data);
  return result.lastInsertRowid as number;
}

export function getAvailableHeatmapDates(): string[] {
  const db = getDb();
  const rows = db
    .prepare('SELECT date FROM market_heatmap_snapshots ORDER BY date DESC LIMIT 30')
    .all() as { date: string }[];
  return rows.map((row) => row.date);
}

export function deleteOldHeatmapSnapshots(keepDays: number = 30): number {
  const db = getDb();
  const result = db
    .prepare(`
      DELETE FROM market_heatmap_snapshots
      WHERE date < date('now', '-' || ? || ' days')
    `)
    .run(keepDays);
  return result.changes;
}

// ---------------------------------------------------------------------------
// Console: Summarization Queue
// ---------------------------------------------------------------------------

export interface SummarizationQueueItem {
  id: number;
  title: string;
  feedName: string;
  categorySlug: string;
  publishedAt: string | null;
  fetchedAt: string;
}

export function getSummarizationQueue(limit: number = 20): SummarizationQueueItem[] {
  const db = getDb();
  const rows = db
    .prepare(`
      SELECT
        a.id,
        a.title,
        f.name as feed_name,
        c.slug as category_slug,
        a.published_at,
        a.fetched_at
      FROM articles a
      LEFT JOIN feeds f ON a.feed_id = f.id
      LEFT JOIN categories c ON f.category_id = c.id
      WHERE (a.summary IS NULL OR a.summary = '')
      ORDER BY a.fetched_at DESC
      LIMIT ?
    `)
    .all(limit) as any[];

  return rows.map(row => ({
    id: row.id,
    title: row.title,
    feedName: row.feed_name || 'Unknown',
    categorySlug: row.category_slug || 'unknown',
    publishedAt: row.published_at,
    fetchedAt: row.fetched_at,
  }));
}

export function getSummarizationQueueCount(): number {
  const db = getDb();
  const row = db
    .prepare(`
      SELECT COUNT(*) as count
      FROM articles
      WHERE (summary IS NULL OR summary = '')
    `)
    .get() as { count: number };
  return row.count;
}

export function getManualLinksFeedId(): number | null {
  const db = getDb();
  const row = db
    .prepare("SELECT id FROM feeds WHERE url = 'internal://manual'")
    .get() as { id: number } | undefined;
  return row?.id ?? null;
}

export function createManualArticle(data: {
  url: string;
  title: string;
  content?: string;
  imageUrl?: string;
  author?: string;
}): number | null {
  const db = getDb();
  const feedId = getManualLinksFeedId();

  if (!feedId) {
    throw new Error("Manual Links feed not found");
  }

  // Generate GUID from URL hash to prevent duplicates
  const urlHash = createHash('sha256').update(data.url).digest('hex');
  const guid = `manual-${urlHash.slice(0, 32)}`;

  const result = db
    .prepare(
      `INSERT OR IGNORE INTO articles
        (feed_id, guid, title, link, author, published_at, content, image_url)
       VALUES (?, ?, ?, ?, ?, datetime('now'), ?, ?)`
    )
    .run(
      feedId,
      guid,
      data.title,
      data.url,
      data.author ?? "Manual Entry",
      data.content ?? null,
      data.imageUrl ?? null
    );

  if (result.changes === 0) return null;
  return result.lastInsertRowid as number;
}

export function deleteManualArticle(id: number): boolean {
  const db = getDb();
  const feedId = getManualLinksFeedId();
  if (!feedId) return false;

  const result = db
    .prepare("DELETE FROM articles WHERE id = ? AND feed_id = ?")
    .run(id, feedId);
  return result.changes > 0;
}

export function createArticlesFromSearchResults(
  results: Array<{ title: string; url: string; description?: string }>,
  parentUrl: string
): number[] {
  const db = getDb();
  const feedId = getManualLinksFeedId();

  if (!feedId || results.length === 0) {
    return [];
  }

  // Generate parent hash (same way as createManualArticle and getSearchResults)
  const parentUrlHash = createHash("sha256").update(parentUrl).digest("hex").slice(0, 32);

  const createdIds: number[] = [];

  for (let i = 0; i < results.length; i++) {
    const result = results[i];
    // Use parent hash + index for GUID (matches getSearchResults pattern)
    const guid = `${parentUrlHash}-${i}`;

    const insertResult = db
      .prepare(
        `INSERT OR IGNORE INTO articles
          (feed_id, guid, title, link, author, published_at, content)
         VALUES (?, ?, ?, ?, ?, datetime('now'), ?)`
      )
      .run(
        feedId,
        guid,
        result.title,
        result.url,
        "Search Result",
        result.description || null
      );

    if (insertResult.changes > 0) {
      createdIds.push(insertResult.lastInsertRowid as number);
    }
  }

  return createdIds;
}

export function getSearchResults(articleUrl: string): Article[] {
  const db = getDb();
  const feedId = getManualLinksFeedId();

  if (!feedId) {
    return [];
  }

  // Generate the parent GUID the same way as createManualArticle
  const urlHash = createHash("sha256").update(articleUrl).digest("hex");
  const parentGuid = `manual-${urlHash.slice(0, 32)}`;

  // Find the parent article
  const parentArticle = db
    .prepare(
      `SELECT id FROM articles
       WHERE feed_id = ? AND guid = ?`
    )
    .get(feedId, parentGuid) as { id: number } | undefined;

  if (!parentArticle) {
    return [];
  }

  // Get articles that were created from this search
  // These are identified by having a guid starting with the parent's URL hash
  const results = db
    .prepare(
      `SELECT a.*, f.name AS feed_name, c.slug AS category_slug
       FROM articles a
       JOIN feeds f ON a.feed_id = f.id
       JOIN categories c ON f.category_id = c.id
       WHERE a.feed_id = ? AND a.guid LIKE ?
       AND a.guid != ?
       LIMIT 5`
    )
    .all(feedId, `${urlHash.slice(0, 32)}-%`, parentGuid) as any[];

  return results.map(mapArticleRow);
}
