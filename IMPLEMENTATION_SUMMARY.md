# Smart Article Selection — Implementation Summary

## Overview
Successfully implemented a smart article ranking and selection system that limits Finance, Gaming, Sports, and World News categories to the top 20 most relevant articles per day based on user preferences, article importance, and popularity.

---

## ✅ Completed Features

### 1. Database Schema
- **New columns in `articles` table:**
  - `relevance_score` (REAL) — 0-100 article ranking score
  - `is_promoted` (INTEGER) — 1 for top 20 articles, 0 otherwise
- **New column in `feeds` table:**
  - `source_weight` (REAL) — User-configurable feed importance (0.5-2.0, default 1.0)
- **New `user_preferences` table:**
  - Stores keyword preferences per category (auto-extracted from saved articles + manual)
  - Tracks keyword weight and source (auto/manual)
- **Indexes added** for performance on promoted articles and relevance scores
- **Migration logic** included for existing databases

### 2. Article Scoring Engine (`src/lib/ranking/scorer.ts`)
Multi-signal scoring algorithm (0-100 scale):
- **Group size (30%)**: Articles covered by more sources rank higher
- **Preference match (30%)**: Keyword similarity to user's saved article patterns
- **Source weight (20%)**: User-configured feed reputation
- **Recency (10%)**: Newer articles within 24h get boost
- **Title importance (10%)**: BREAKING, EXCLUSIVE, etc. keywords

### 3. Preference Learning (`src/lib/ranking/preferences.ts`)
- **Auto-extracts keywords** from saved article titles
- **Filters stop words** and normalizes to meaningful terms
- **Weights keywords** by frequency across saved articles
- **Debounced rebuild** (max once per 5 min) when articles are saved
- **Manual preferences** can be added via API

### 4. Daily Promotion Logic (`src/lib/ranking/promoter.ts`)
- Scores all articles from last 24h in each category
- Promotes top 20 by relevance score
- Only applies to: `finance`, `gaming`, `sports`, `world-news`
- Resets daily automatically

### 5. Integration with Feed Refresh Pipeline
- **Scheduler** (`src/lib/rss/scheduler.ts`) — Runs scoring + promotion after feed refresh
- **Manual refresh API** (`src/app/api/feeds/refresh/route.ts`) — Same pipeline
- **Sequence**: fetch → dedup → insert → group → **SCORE → PROMOTE** → summarize

### 6. Updated Article Queries
- `getArticlesByCategory()` — New `promotedOnly` option (default: true for capped categories)
- `getArticleGroupsByCategory()` — Filters groups where representative is promoted
- Default behavior: Show only promoted articles in capped categories

### 7. UI Enhancements
- **Toggle link** on homepage for capped categories: "Showing top 20 • Show all articles"
- **Top Pick badge** (★) on promoted articles with relevance score tooltip
- **Visual indicators** in list view and standard card layouts
- Query param `?showAll=true` to view all articles

### 8. Settings Page — Feed Rankings
- **Feed Weights section** in `/settings` (collapsible)
- **Weight selector per feed**: Low (0.5×), Normal (1.0×), High (1.5×), Essential (2.0×)
- Only shows feeds from capped categories
- Updates immediately via PATCH API

### 9. Preference Rebuild Trigger
- When user saves/unsaves article, triggers debounced preference rebuild
- Integrated in `PATCH /api/articles/[id]` handler
- Non-blocking, fire-and-forget operation

### 10. API Endpoints
- **`GET/POST/DELETE/PUT /api/preferences`** — Manage preference keywords
  - GET: Retrieve keywords (all or by category)
  - POST: Add/update keyword (manual or auto)
  - DELETE: Remove keyword by ID
  - PUT: Manually trigger preference rebuild
- **`GET/PATCH /api/feeds/weights`** — Manage feed source weights
  - GET: List all feeds with weights
  - PATCH: Update feed weight (0.1-2.0 range)

---

## Architecture Highlights

### Data Flow
```
User saves articles
  ↓
Preference keywords extracted (debounced)
  ↓
RSS feeds refresh every 15 min
  ↓
Articles fetched, deduped, inserted, grouped
  ↓
Articles scored (group size + prefs + source + recency + title)
  ↓
Top 20 per category promoted (is_promoted=1)
  ↓
UI shows promoted articles by default
```

### Scoring Example
Article: "Apple reports record revenue amid AI boom"
- Group size: 4 sources → 24 points (out of 30)
- Preference match: User saved articles about "Apple", "AI" → 22 points (out of 30)
- Source weight: Bloomberg = 1.5× → 15 points (out of 20)
- Recency: Published 3 hours ago → 10 points (out of 10)
- Title importance: "record" keyword → 3 points (out of 10)
- **Total score: 74/100** → Likely promoted

---

## File Changes

| File | Type | Description |
|------|------|-------------|
| `src/lib/db/schema.ts` | Modified | Added tables, columns, indexes, migration |
| `src/lib/db/queries.ts` | Modified | Added 15+ ranking queries, updated mappers |
| `src/types/index.ts` | Modified | Added `relevanceScore`, `isPromoted` to Article |
| **`src/lib/ranking/preferences.ts`** | **New** | Keyword extraction & preference matching |
| **`src/lib/ranking/scorer.ts`** | **New** | Multi-signal article scoring engine |
| **`src/lib/ranking/promoter.ts`** | **New** | Daily top-20 selection logic |
| `src/lib/rss/scheduler.ts` | Modified | Integrated scoring after grouping |
| `src/app/api/feeds/refresh/route.ts` | Modified | Integrated scoring after grouping |
| `src/app/api/articles/[id]/route.ts` | Modified | Trigger preference rebuild on save |
| **`src/app/api/preferences/route.ts`** | **New** | Preference keywords CRUD API |
| **`src/app/api/feeds/weights/route.ts`** | **New** | Feed weight management API |
| `src/app/page.tsx` | Modified | Added `promotedOnly` filter + toggle UI |
| `src/components/articles/ArticleCard.tsx` | Modified | Added Top Pick badge & star indicator |
| `src/app/settings/page.tsx` | Modified | Added Feed Rankings section |

---

## Testing Checklist

1. ✅ Schema migration runs on existing DB (fixed: indexes created after column migration)
2. ⏳ Feed refresh scores & promotes articles
3. ⏳ Top 20 articles displayed by default in capped categories
4. ⏳ "Show all" toggle works correctly
5. ⏳ Saving articles triggers preference rebuild
6. ⏳ Preference keywords extracted from saved articles
7. ⏳ Feed weights adjustable in Settings
8. ⏳ Articles from higher-weighted feeds score better
9. ⏳ Top Pick badge displays on promoted articles
10. ⏳ Manual preference API endpoints work

---

## Next Steps

1. **Test the system**: Run feed refresh and verify scoring works
2. **Save some articles**: Check if preference keywords are extracted
3. **Adjust feed weights**: Test if scoring reflects weight changes
4. **UI polish**: Review Top Pick badge styling
5. **Performance**: Monitor query performance with large article counts
6. **Optional**: Add preference management UI in Settings (currently API-only)

---

## Configuration

- **Capped categories**: `["finance", "gaming", "sports", "world-news"]`
- **Daily article limit**: `20` per category
- **Preference rebuild debounce**: `5 minutes`
- **Feed weight range**: `0.1 - 2.0` (default: `1.0`)
- **Relevance score range**: `0 - 100`

To modify these, edit constants in:
- `src/lib/db/queries.ts` — `CAPPED_CATEGORIES`, `DAILY_ARTICLE_LIMIT`
- `src/lib/ranking/preferences.ts` — `REBUILD_DEBOUNCE_MS`
- `src/lib/ranking/scorer.ts` — Scoring weights and thresholds
