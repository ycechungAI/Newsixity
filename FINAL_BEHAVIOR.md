# Smart Article Ranking System - Final Behavior

## Overview
The system scores and ranks articles to help identify the most important ones, but **ALL articles remain visible**.

---

## ✅ What Happens

### On Feed Refresh (Every 15 Minutes):

1. **All articles are fetched** from RSS feeds
2. **All articles are stored** in the database
3. **Articles are scored** (0-100) using:
   - Group size (30%) - How many sources cover this story
   - Your preferences (30%) - Keywords from articles you've saved
   - Source weight (20%) - Feed reputation you configured
   - Recency (10%) - How fresh the article is
   - Title importance (10%) - BREAKING, EXCLUSIVE, etc.

4. **Top 20 articles per day are marked as promoted**
   - Only applies to: `finance`, `gaming`, `sports`, `world-news`
   - These get a "★ Top Pick" badge in the UI
   - Does NOT apply to: `top-news`, `technology`, `weather`, `others`

5. **ALL articles remain visible**
   - Nothing is deleted
   - You see everything from all categories
   - Old articles, new articles, promoted, unpromoted - all visible

---

## 🎯 What You See

### Every Category Shows All Its Articles:
- **Finance** - All articles (with top 20/day marked with ★)
- **Gaming** - All articles (with top 20/day marked with ★)
- **Sports** - All articles (with top 20/day marked with ★)
- **World News** - All articles (with top 20/day marked with ★)
- **Top News** - All articles (no scoring/promotion)
- **Technology** - All articles (no scoring/promotion)
- **Others** - All articles (your manual links)
- **Saved** - All saved articles

### Visual Indicators:
- **★ Top Pick** badge - Appears on promoted articles
- Shows relevance score in tooltip
- No filtering or hiding of any articles

---

## 📊 Current Database Stats

```
Finance:      76 articles (2 saved)
Gaming:       193 articles
Sports:       31 articles (1 saved)
Technology:   121 articles
Top News:     46 articles (3 saved)
World News:   30 articles (1 saved)

Total Saved:  7 articles
```

---

## 🔧 How Scoring Works

### Algorithm (0-100 scale):
```
Score = GroupSize(30) + Preferences(30) + SourceWeight(20) + Recency(10) + TitleImportance(10)
```

### Example:
**Article:** "Apple reports record revenue amid AI boom"

- **Group size:** 4 sources → 24 points (4/5 × 30)
- **Preference match:** User saved articles about "Apple", "AI" → 22 points
- **Source weight:** Bloomberg = 1.5× → 15 points
- **Recency:** Published 3 hours ago → 10 points
- **Title importance:** "record" keyword → 3 points
- **Total:** 74/100 → Likely gets ★ Top Pick badge

---

## 🛠️ User Controls

### 1. Feed Rankings (Settings Page)
Adjust source weights to influence scoring:
- **Low (0.5×)** - Less important sources
- **Normal (1.0×)** - Default weight
- **High (1.5×)** - More important sources
- **Essential (2.0×)** - Critical sources

### 2. Automatic Preferences
- System learns from articles you save
- Extracts keywords from saved article titles
- Weights keywords by frequency
- Rebuilds every time you save/unsave (debounced to 5 min)

### 3. Manual Preferences (API)
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

## 📝 Configuration

Edit in `src/lib/db/queries.ts`:

```typescript
// Which categories get scoring/promotion
export const CAPPED_CATEGORIES = ["finance", "gaming", "sports", "world-news"];

// How many articles per day get promoted
export const DAILY_ARTICLE_LIMIT = 20;
```

---

## 🎨 UI Features

### Article Cards Show:
- Title, source, timestamp, image
- ★ Top Pick badge (for promoted articles)
- Relevance score tooltip
- AI summary checkmark
- Save/read status

### No Filtering:
- All articles visible by default
- No toggle needed
- No pagination differences
- Simple, clean presentation

---

## 💾 Data Persistence

**Everything is kept:**
- ✅ All articles from all time
- ✅ All saved articles (protected)
- ✅ All manual links in "Others"
- ✅ Article scoring metadata
- ✅ User preferences
- ✅ Feed configurations

**Nothing is deleted.**

---

## 🚀 Summary

**Purpose:** Intelligent article ranking to highlight what matters most
**Method:** Multi-signal scoring based on coverage, preferences, source, timing
**Display:** ALL articles visible, with top picks marked
**Result:** You see everything + know what's most important
