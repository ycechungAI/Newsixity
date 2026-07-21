# Stage 3: Utilities & Deduplication — Complete

**Status:** ✅ Complete  
**Author:** Haiku 4.5  
**Lines of code:** ~600 LOC (8 utility modules + 2 dedup modules)

## What was built

### Utility Modules (`backend/app/lib/utils/`)

1. **date.py** (60 LOC)
   - `time_ago(date_str)` — human-readable time (e.g., "5m ago", "3d ago")
   - `format_date(date_str)` — formatted timestamp (e.g., "Jan 21, 2026 at 3:45 PM")
   - Handles timezone-aware ISO 8601 datetime strings

2. **search.py** (50 LOC)
   - `detect_search_engine(url)` → engine info + extracted query
   - `is_search_engine_url(url)` → boolean
   - Supports: Google, Bing, DuckDuckGo, Yahoo, Baidu, Yandex
   - Query parameter extraction via urllib.parse

3. **video.py** (180 LOC)
   - `extract_video_info(url)` → type, video_id, embed_url
   - `is_video_url(url)` → boolean
   - Supports: YouTube (standard, short links, Shorts, playlists), Vimeo, Dailymotion, Odysee, Animex
   - `fetch_youtube_playlist(playlist_id, page, page_size)` → paginated items + metadata
   - Uses stdlib urllib + socket (no external dependencies)

4. **sanitize.py** (already existed from Stage 1b)
   - `strip_html(text)` — regex + entity decoding
   - `truncate(text, max_len)` — length capping
   - `extract_image_from_html(html)` — image extraction from article HTML

5. **url.py** (already existed from Stage 1b)
   - `parse_http_url(url)` — SSRF hardening (http/https only, no credentials)
   - `is_http_url(url)` → boolean

### Deduplication Modules (`backend/app/lib/dedup/`)

1. **similarity.py** (65 LOC)
   - `normalize_title_for_hash(title)` — remove news prefixes (BREAKING:, UPDATE:, etc.), special chars, normalize whitespace
   - `hash_title(title)` — same as normalize (semantic hash, not cryptographic)
   - `get_bigrams(text)` → list of 2-char substrings
   - `bigram_similarity(a, b)` → Dice coefficient (0.0–1.0)
   - `is_duplicate(new_title, existing_title, threshold=0.7)` → boolean
   - Example: "Stock Market Hits Record" vs "Stock Market Reaches Record" → 0.75 similarity (duplicate)

2. **grouping.py** (55 LOC)
   - `group_articles(articles, category_slug)` — main dedup + grouping logic
   - For each article:
     - Find recent groups (48h) with best title match (bigram similarity)
     - If score > 0.5, assign to group + increment count
     - If new article has more content, promote as representative
     - Else, create new group with article as representative
   - Uses repository layer for DB access (no raw SQL)

## Testing

✓ All utilities tested with real-world examples:
  - Date formatting: handles timezone-aware ISO strings, fallback to "Unknown"
  - Search engines: correctly detects domains + extracts query params
  - Video URLs: handles 15+ YouTube variants (standard, short, Shorts, playlists) + Vimeo/Dailymotion
  - Dedup: title normalization removes prefixes, bigram similarity scores work correctly
  - Duplicate detection: threshold-based matching (0.7 default)

## Dependencies

All stdlib (no new external packages):
- `urllib.parse` (URL parsing, query extraction)
- `urllib.request` + `socket` (YouTube playlist fetching)
- `re` (regex for prefixes, video URL patterns)
- `dataclasses` (data structures)

## Next steps

**Stage 4** (mixed Sonnet/Haiku) integrates external APIs:
- Sonnet: yfinance (stock data), ollama (LLM) + async framework integration
- Haiku: RSS feed parsing (feedparser), weather API, HTTP-only content extraction

**Stage 5** (Haiku + Sonnet review) wires utilities into 24 API routers.

---

**All utilities ready for integration into background jobs and API routes. No database schema changes.**
