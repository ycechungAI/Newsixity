# Plan: Smart Article Selection — Top 20 Per Category Per Day

## Goal
Be more selective about which articles appear in the feed. Limit each target category (Finance, Gaming, Sports, World News) to the **top 20 articles per day**, ranked by a combination of user preferences, article importance, and popularity.

---

## Architecture Overview

**Strategy: Score at ingest + filter at display.**
- All articles are still fetched and stored (no data loss)
- Each article gets a `relevance_score` (0-100) computed at fetch time
- A new `is_promoted` flag marks the daily top 20 per category
- Default views show only promoted articles; a toggle shows all

**Scoring signals (weighted):**

| Signal | Weight | Description |
|--------|--------|-------------|
| **Group size** | 30% | Articles covered by more sources = more important (already tracked via `article_groups.article_count`) |
| **Preference match** | 30% | Keyword similarity to user's saved articles (title bigram matching against preference profile) |
| **Source weight** | 20% | Configurable feed reputation (default: equal; user can boost/demote feeds) |
| **Recency** | 10% | Published within last 6h = full score, decays over 24h |
| **Title importance** | 10% | Bonus for BREAKING, EXCLUSIVE, key event words |

---

## Step-by-Step Implementation

### Step 1: Schema Changes
**File: `src/lib/db/schema.ts`**

Add columns to `articles` table:
```sql
ALTER TABLE articles ADD COLUMN relevance_score REAL DEFAULT 0;
ALTER TABLE articles ADD COLUMN is_promoted INTEGER NOT NULL DEFAULT 0;
```

Add `source_weight` column to `feeds` table:
```sql
ALTER TABLE feeds ADD COLUMN source_weight REAL NOT NULL DEFAULT 1.0;
```

Add new table for preference keywords:
```sql
CREATE TABLE IF NOT EXISTS user_preferences (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category_slug TEXT NOT NULL,
  keyword TEXT NOT NULL,
  weight REAL NOT NULL DEFAULT 1.0,
  source TEXT NOT NULL DEFAULT 'auto',  -- 'auto' from saved articles, 'manual' from user
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(category_slug, keyword)
);
```

Add new index:
```sql
CREATE INDEX IF NOT EXISTS idx_articles_promoted ON articles(is_promoted) WHERE is_promoted = 1;
CREATE INDEX IF NOT EXISTS idx_articles_relevance ON articles(relevance_score DESC);
CREATE INDEX IF NOT EXISTS idx_user_preferences_category ON user_preferences(category_slug);
```

Add migration logic in `src/lib/db/index.ts` to ALTER TABLE for existing databases.

### Step 2: Preference Learning Module
**New file: `src/lib/ranking/preferences.ts`**

Build a keyword preference profile from saved articles:
- Query all `is_saved = 1` articles per category
- Extract meaningful keywords from titles (remove stop words, normalize)
- Weight keywords by frequency (more saves with keyword = higher weight)
- Store/update in `user_preferences` table
- Rebuild periodically (after each save toggle, throttled to max once per 5 min)

Key functions:
- `rebuildPreferences(categorySlug?: string)` — scan saved articles, extract keywords, update table
- `getPreferenceKeywords(categorySlug: string)` — return weighted keyword list
- `scorePreferenceMatch(title: string, keywords: WeightedKeyword[])` — 0-1 score

### Step 3: Article Scoring Module
**New file: `src/lib/ranking/scorer.ts`**

Compute a 0-100 relevance score for each article:

```typescript
interface ScoringContext {
  article: Article;
  groupSize: number;          // from article_groups.article_count
  feedSourceWeight: number;   // from feeds.source_weight
  preferenceKeywords: WeightedKeyword[];
}

function scoreArticle(ctx: ScoringContext): number {
  const groupScore = Math.min(ctx.groupSize / 5, 1.0) * 30;       // 0-30
  const prefScore = scorePreferenceMatch(ctx.article.title, ctx.preferenceKeywords) * 30;  // 0-30
  const sourceScore = Math.min(ctx.feedSourceWeight, 2.0) / 2.0 * 20;  // 0-20
  const recencyScore = computeRecencyScore(ctx.article.publishedAt) * 10;  // 0-10
  const importanceScore = computeTitleImportance(ctx.article.title) * 10;  // 0-10
  return groupScore + prefScore + sourceScore + recencyScore + importanceScore;
}
```

### Step 4: Daily Promotion Logic
**New file: `src/lib/ranking/promoter.ts`**

After scoring, select top 20 per category per day:

```typescript
function promoteTopArticles(categorySlug: string, dailyLimit: number = 20): void {
  // 1. Reset is_promoted for articles older than today in this category
  // 2. Get all unread articles from today, ordered by relevance_score DESC
  // 3. Mark top N as is_promoted = 1
  // 4. Store the daily cutoff score for reference
}
```

Called after:
- Feed refresh (scheduler + manual refresh)
- Article grouping completes (group size may change scores)

### Step 5: Integrate Scoring into Feed Refresh Pipeline
**Files: `src/lib/rss/scheduler.ts`, `src/app/api/feeds/refresh/route.ts`**

After grouping new articles, add scoring + promotion step:

```
Existing pipeline:
  fetch → dedup → insert → group → summarize

New pipeline:
  fetch → dedup → insert → group → SCORE → PROMOTE → summarize
```

In both `refreshAllFeeds()` and the `POST /api/feeds/refresh` handler:
1. After `groupArticles()`, call `scoreNewArticles(categorySlug, articleIds)`
2. After scoring all categories, call `promoteTopArticles(categorySlug)` for each affected category

### Step 6: Update Article Queries for Promotion Filter
**File: `src/lib/db/queries.ts`**

- Modify `getArticlesByCategory()` to accept `{ promotedOnly?: boolean }` option
  - When true: add `AND a.is_promoted = 1` to WHERE clause
  - Default: `true` for the 4 target categories, `false` for others
- Modify `getArticleGroupsByCategory()` similarly — only show groups where representative is promoted
- Add new query: `getDailyArticleCount(categorySlug: string)` — count promoted articles for today

### Step 7: UI — "Show All" Toggle
**File: `src/app/page.tsx` and `src/components/articles/ArticleList.tsx`**

- Add a toggle/link: "Showing top 20 — Show all articles"
- When toggled, re-fetch with `promotedOnly=false`
- Show relevance score as a subtle indicator (e.g., small bar or number) on article cards
- Show "Top Pick" badge on promoted articles when viewing all

### Step 8: UI — Source Weight Configuration
**File: `src/app/settings/page.tsx`**

Add a "Feed Rankings" section in Settings:
- List all feeds grouped by category
- Each feed has a slider or dropdown: Low (0.5) / Normal (1.0) / High (1.5) / Essential (2.0)
- Saves to `feeds.source_weight` column

### Step 9: Preference Rebuild Trigger
**File: `src/app/api/articles/[id]/route.ts`**

When an article is saved/unsaved (PATCH handler):
- After toggling `is_saved`, fire a debounced preference rebuild
- Use a global timer to avoid rebuilding more than once per 5 minutes

### Step 10: API Endpoint for Manual Preference Keywords
**New file: `src/app/api/preferences/route.ts`**

- `GET /api/preferences` — return current preference keywords by category
- `POST /api/preferences` — add/update manual keyword with weight
- `DELETE /api/preferences` — remove a keyword

This lets users explicitly say "I care about AI, crypto, Nintendo" etc.

---

## Categories Affected

The daily cap of 20 applies to these categories:
- **Finance** (`finance`)
- **Gaming** (`gaming`)
- **Sports** (`sports`)
- **World News** (`world-news`)

Other categories (Technology, Weather, Top News, Others) keep current behavior — no cap, show everything.

This is configurable via a constant or settings.

---

## Data Flow Summary

```
User saves articles
  → preference keywords extracted & stored
  → future articles scored against preferences

RSS feeds refresh (every 15 min)
  → articles fetched, deduped, inserted
  → articles grouped (coverage count)
  → articles SCORED (group size + prefs + source weight + recency + title)
  → top 20 per category PROMOTED for today
  → UI shows promoted articles by default
```

---

## File Changes Summary

| File | Change |
|------|--------|
| `src/lib/db/schema.ts` | Add columns, new table, indexes |
| `src/lib/db/index.ts` | Migration for existing DBs |
| `src/lib/db/queries.ts` | Add `promotedOnly` filter, new queries |
| **`src/lib/ranking/preferences.ts`** | NEW — keyword extraction & preference matching |
| **`src/lib/ranking/scorer.ts`** | NEW — multi-signal article scoring |
| **`src/lib/ranking/promoter.ts`** | NEW — daily top-20 selection |
| `src/lib/rss/scheduler.ts` | Add scoring + promotion after grouping |
| `src/app/api/feeds/refresh/route.ts` | Add scoring + promotion after grouping |
| `src/app/api/articles/[id]/route.ts` | Trigger preference rebuild on save |
| **`src/app/api/preferences/route.ts`** | NEW — preference keyword CRUD |
| `src/app/page.tsx` | Add "Show all" toggle |
| `src/components/articles/ArticleList.tsx` | Promotion filter + badge |
| `src/app/settings/page.tsx` | Feed weight configuration |

---

## Implementation Order

1. Schema changes + migration (Step 1)
2. Preference learning (Step 2)
3. Scoring engine (Step 3)
4. Promotion logic (Step 4)
5. Pipeline integration (Step 5)
6. Query changes (Step 6)
7. UI toggle (Step 7)
8. Settings UI for feed weights (Step 8)
9. Save trigger for preference rebuild (Step 9)
10. Manual preferences API (Step 10)
