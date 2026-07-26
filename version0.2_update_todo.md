# Newsixity Roadmap

## Version 0.1 (Released)
✅ Initial desktop app with Tauri packaging (macOS, Windows, Linux)
✅ Core news aggregation with RSS feeds
✅ Article reading, saving, and search
✅ Finance/stock quotes integration (yfinance)
✅ Summarization with Ollama
✅ Auto-backup and manual backup features
✅ Cross-platform database and app-data management

---

## Version 0.2 (Next)

### Feature: Sports Section Expansion
**Goal:** Expand sports coverage beyond basketball to a comprehensive multi-sport experience

- [ ] Add tennis feed sources (ATP, WTA, major tournaments)
- [ ] Add world sports feeds (international competitions)
- [ ] Add Olympics/Paralympics event feeds
- [x] Add sports feeds (tennis, soccer/football, Canadian sports)
- [ ] Add international sports sources
- [ ] Add Canadian sports player feeds (filter by Canadian athletes across all sports)
- [ ] Create sports category/tab in UI with subcategory filtering
- [ ] Implement sport-specific feed management (enable/disable individual sports)
- [ ] Testing: verify all sports feeds populate correctly and updates work

### Feature: Hacker News / Security News Tab
**Goal:** Add dedicated tab for security, data breaches, and hacker-focused news

- [ ] Research and integrate databreaches.net feed
- [ ] Add other security news sources (HackerNews, SecurityWeekly, etc.)
- [ ] Create "Security/Hacker News" tab in UI
- [ ] Implement feed parsing for security-specific content
- [ ] Add filtering for breach severity/type (optional enhancement)
- [ ] Testing: verify security feeds fetch and display properly

### Feature: Podcast Tab & Management
**Goal:** Enable podcast discovery, management, and listening from within the app

**Core Functionality:**
- [ ] Add podcast feed support (RSS podcast feeds)
- [ ] Create "Podcasts" tab in main UI
- [ ] Implement podcast discovery/search
- [ ] Add ability to subscribe to podcasts
- [ ] Add ability to remove subscriptions
- [ ] Display podcast episodes with metadata (title, date, duration)

**Favorite/Bookmark System:**
- [ ] Add podcast-level favorites (favorite shows)
- [ ] Add episode-level favorites (favorite episodes)
- [ ] Display favorites in a dedicated section
- [ ] Persist favorites to database

**Playback:**
- [ ] Embed audio player in app (web audio API or similar)
- [ ] Play episode audio directly in app
- [ ] Track playback progress (time listened)
- [ ] Support play/pause/seek controls
- [ ] Optional: speed control (1x, 1.25x, 1.5x, etc.)

**Database:**
- [ ] Create podcast_feeds table
- [ ] Create podcast_episodes table
- [ ] Create podcast_favorites table
- [ ] Schema migrations for clean rollout

**Testing:**
- [ ] Test podcast feed parsing (various feed formats)
- [ ] Test playback on macOS, Windows, Linux
- [ ] Test favorites persistence
- [ ] Test episode progress tracking

### Maintenance & Code Quality
**Bug Fixes:**
- [ ] Review and fix any reported v0.1 issues
- [ ] Test app lifecycle (startup, shutdown, crash recovery)
- [ ] Verify database integrity across versions
- [ ] Test backup/restore on all platforms

**Maintainability:**
- [ ] Refactor backend feed parsing to support podcasts
- [ ] Consolidate feed source management (reduce duplication)
- [ ] Add logging for feed fetch errors and retries
- [ ] Update type hints and add missing docstrings
- [ ] Improve test coverage (add integration tests for new tabs)
- [ ] Clean up unused dependencies
- [ ] Document podcast schema and feed handling
- [ ] Update desktop.md with podcast and expanded sports docs

**Performance:**

Carried over from `To DO.md` (items 19–24) after auditing which survived the
Next.js → FastAPI/Vite migration. Items 20 and 22 were fixed during the port;
24 moved off the request path. These three are still live, with current paths:

- [x] **Batch "mark read" requests.** Done — new `PATCH /api/articles` bulk
      endpoint + a module-level queue (`src/lib/articles/markReadQueue.ts`)
      shared across every `ArticleCard`, replacing the old per-card
      `IntersectionObserver` → individual `PATCH /api/articles/{id}` calls.
      Verified: a 30-card page produces exactly one batched request.
- [x] **Batch the post-refresh article fetch.** Done — `refresh.py` uses
      `get_articles_by_ids()` (single `WHERE id IN (...)` query).
- [x] **Add the `(is_read, published_at)` compound index.** Done —
      `idx_articles_is_read_published` in `models.py` + explicit
      `CREATE INDEX IF NOT EXISTS` in `init_db.py`.

New-feature performance work:
- [ ] Profile app startup time with podcast feeds enabled
- [ ] Optimize database queries for new tables
- [ ] Monitor memory usage with large podcast subscriptions
- [ ] Implement pagination for long episode lists (if needed)

**Doc consolidation:**
- [x] Retired `To DO.md` — all items resolved (1–18 pre-migration, 19/21/23
      above, 20/22 confirmed fixed in the port).
- [x] Triaged the root-level planning docs. Folded into `docs/`:
      `BACKUP_SYSTEM.md` → `docs/backup.md` (corrected: retention is 2 most
      recent, not "forever"), `FINAL_BEHAVIOR.md` → `docs/ranking.md`
      (confirmed accurate — ranking never deletes articles, only badges
      them), `DEEP-RESEARCH-SETUP.md` → `docs/deep-research.md` (corrected
      Bing → DuckDuckGo HTML fallback). Deleted as obsolete: `PLAN.md`,
      `BUGS.md`, `IMPLEMENTATION_SUMMARY.md`, `DEEP-RESEARCH-TODO.md`,
      `BEHAVIOR_SUMMARY.md` (contradicted `FINAL_BEHAVIOR.md` — described a
      deletion-based design that was explicitly disabled, never shipped),
      `STARTUP.md` (wrong port/browser, non-reproducible LaunchAgent).
      `README.md` and `docs/DEVELOPER_GUIDE.md` were also still describing
      the pre-migration Next.js stack — rewritten for FastAPI + Vite.

---

## Version 0.3 (Future)
- Audio transcription of podcast episodes (via Ollama or external service)
- Podcast episode transcripts search
- Social sharing of articles and episodes
- Multi-device sync (cloud backup)
- Advanced filtering and saved searches
- Dark mode refinements

---

## Known Issues & Technical Debt
- [ ] ThemeProvider React Fast Refresh warning (low priority)
- [ ] GitHub Actions security vulnerability (Dependabot flagged)
- [ ] Backend code organization: consolidate feed fetching logic
