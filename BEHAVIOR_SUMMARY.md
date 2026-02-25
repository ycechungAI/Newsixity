# Smart Article Selection — How It Works

## Overview
The system limits Finance, Gaming, Sports, and World News to **20 new articles per day** based on intelligent scoring. Old articles remain visible forever.

---

## ✅ What Happens

### On Feed Refresh (Every 15 Minutes):

1. **All articles are fetched** from RSS feeds (as normal)
2. **Articles are scored** using:
   - Group size (30%) - How many sources cover this story
   - Your preferences (30%) - Keywords from articles you've saved
   - Source weight (20%) - Feed reputation you configured
   - Recency (10%) - How fresh the article is
   - Title importance (10%) - BREAKING, EXCLUSIVE, etc.

3. **Top 20 articles per day are kept**, rest are deleted
   - Only applies to: `finance`, `gaming`, `sports`, `world-news`
   - Does NOT apply to: `top-news`, `technology`, `weather`, `others`

4. **Old articles stay forever**
   - Only TODAY'S unpromoted articles are deleted
   - Articles from yesterday, last week, etc. remain untouched
   - Your saved articles are never deleted

---

## ✅ What You See

### All Categories Show All Their Articles:
- **Finance/Gaming/Sports/World News** - Shows all articles (today's top 20 + all old articles)
- **Top News** - Shows all articles (no filtering)
- **Technology** - Shows all articles (no filtering)
- **Others** - Shows all articles (your manual links)
- **Saved** - Shows all saved articles (never filtered)

### No UI Toggle:
- There's no "show all" toggle - you always see everything
- The filtering happens at ingestion, not display
- Old posts are always visible

---

## Example Timeline

**Monday Morning** (9 AM):
- Feed refresh fetches 50 finance articles
- System scores all 50
- Top 20 by score are kept, 30 are deleted
- You see: 20 new articles from today

**Monday Afternoon** (3 PM):
- Feed refresh fetches 30 more finance articles
- System scores all 50 articles from today (20 existing + 30 new)
- Top 20 by score are kept, 30 are deleted
- You see: 20 articles from today (some may be different from morning)

**Tuesday Morning** (9 AM):
- Monday's 20 articles remain visible
- Feed refresh fetches 40 new finance articles
- System scores only Tuesday's 40 articles
- Top 20 from Tuesday are kept, 20 are deleted
- You see: 20 from Monday + 20 from Tuesday = 40 total

**Result:** Old articles accumulate, but only 20 new ones added per day.

---

## Technical Details

### Scoring Algorithm (0-100 scale):
```
Score = GroupSize(30) + Preferences(30) + SourceWeight(20) + Recency(10) + TitleImportance(10)
```

### Deletion Logic:
```sql
DELETE FROM articles
WHERE category IN (finance, gaming, sports, world-news)
  AND date(published_at) >= TODAY
  AND is_promoted = 0
```

### What's Protected:
- Articles from before today (any date < today)
- Saved articles (is_saved = 1) - never deleted
- Articles in non-capped categories
- Articles with is_promoted = 1

---

## Configuration

Edit in `src/lib/db/queries.ts`:

```typescript
// Which categories have the 20/day limit
export const CAPPED_CATEGORIES = ["finance", "gaming", "sports", "world-news"];

// How many articles per day per capped category
export const DAILY_ARTICLE_LIMIT = 20;
```

---

## User Controls

### Feed Rankings (Settings Page):
Adjust source weights to influence scoring:
- **Low (0.5×)** - Less important sources
- **Normal (1.0×)** - Default weight
- **High (1.5×)** - More important sources
- **Essential (2.0×)** - Critical sources

### Automatic Preferences:
- System learns from articles you save
- Extracts keywords from saved article titles
- Weights keywords by frequency
- Rebuilds every time you save/unsave (debounced to 5 min)

### Manual Preferences (API):
```bash
# Add a keyword you care about
POST /api/preferences
{
  "categorySlug": "finance",
  "keyword": "bitcoin",
  "weight": 1.5,
  "source": "manual"
}

# View your preferences
GET /api/preferences?category=finance

# Delete a preference
DELETE /api/preferences?id=123
```

---

## Summary

**Ingestion:** Only 20 best articles per day are kept in capped categories
**Display:** All articles (old + today's top 20) are shown
**Result:** You see all your history + a curated selection of today's news
