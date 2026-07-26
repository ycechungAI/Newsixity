# Smart Article Ranking

Newsixity scores and ranks articles to surface the most important ones, but
**all articles remain visible** — nothing is deleted or hidden by the
ranking system. This deliberately replaced an earlier design that deleted
non-promoted articles; see `promoter.py`'s "DELETION IS DISABLED" comment.

## What happens on every feed refresh

1. All articles are fetched and stored, as normal.
2. Articles in the **capped categories** are scored 0–100:
   `backend/app/lib/ranking/scorer.py` (`CAPPED_CATEGORIES` lives in
   `backend/app/db/repository/ranking.py`, currently `finance`, `gaming`,
   `sports`, `world-news`).

   | Signal | Weight | Description |
   |---|---|---|
   | Group size | 30% | Articles covered by more sources rank higher |
   | Preference match | 30% | Keyword similarity to your saved-article history |
   | Source weight | 20% | Feed reputation, user-configurable (0.5–2.0×) |
   | Recency | 10% | Newer articles score higher, decaying over ~24h |
   | Title importance | 10% | Bonus for BREAKING/EXCLUSIVE-style keywords |

3. The top `DAILY_ARTICLE_LIMIT` (20) articles per capped category per day
   are marked `is_promoted = 1` (`backend/app/lib/ranking/promoter.py`).
4. **All articles stay visible in every category** — promoted articles just
   get a "★ top" indicator in the UI (`ArticleCard.tsx`). Non-capped
   categories (`top-news`, `technology`, `weather`, `others`) are never
   scored or promoted.

## Preferences

The system learns from articles you save:
- Keywords are extracted from saved-article titles, stop words filtered.
- Weighted by frequency across your saved articles.
- Stored in the `user_preferences` table, rebuilt automatically (debounced).

Manual keywords via the API (`backend/app/routers/preferences.py`):

```bash
# Add a keyword you care about
POST /api/preferences
{ "categorySlug": "finance", "keyword": "bitcoin", "weight": 1.5, "source": "manual" }

# View preferences
GET /api/preferences?category=finance

# Delete a preference
DELETE /api/preferences?id=123

# Force a rebuild
PUT /api/preferences
```

## Feed weights

Adjust per-feed source weight in Settings (`/settings` → Feed Rankings):
Low (0.5×) · Normal (1.0×) · High (1.5×) · Essential (2.0×).
Backed by `PATCH /api/feeds/weights`, stored on `feeds.source_weight`.

## Configuration

Edit `CAPPED_CATEGORIES` and `DAILY_ARTICLE_LIMIT` in
`backend/app/db/repository/ranking.py`.
