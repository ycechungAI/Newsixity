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

## Version 0.4

### Feature: Ask Newsixity (Perplexity-style Q&A)
**Goal:** Add a query box that returns a synthesized, cited answer instead of a list of articles — the core Perplexity loop. The feed plumbing, summarizer, and article library already provide the infrastructure; this wires them into question-answering.

Implemented 2026-10-01 (Muse): `POST /api/ask` in `backend/app/routers/ask.py`
(registered in `main.py`), `AskRequestBody`/`AskHistoryTurn` in `schemas.py`,
`src/components/ask/AskPage.tsx`, Ask button in `TopBar`, tests in
`backend/tests/integration/test_ask.py`. Sessions are ephemeral — the frontend
keeps the thread and sends prior turns back as `history`; no new DB tables.
Route registration: add `<Route path="/ask" element={<AskPage />} />` next to
the `/search` route. Manual end-to-end checklist: ask with Ollama up (cited
answer, citations resolve to articles), ask with Ollama down (article list,
no synthesis), follow-up keeps context, `pytest backend/tests/integration/test_ask.py`,
`test_api_contract.py` still green, rebuild desktop (`./build-desktop-mac.sh`).

- [x] Add "Ask" query box to TopBar (or a dedicated Ask tab)
- [x] Retrieve relevant articles from the local DB for the query (search over fetched article content)
- [x] Synthesize a cited answer with Ollama (reuse research prompt: answer ONLY from provided sources, cite [1], [2], ...)
- [x] Render answer with clickable source citations linking back to articles
- [x] Support follow-up questions in the same session (conversational thread)
- [x] Graceful fallback when Ollama is offline: show matching articles without synthesis
- [x] Testing: verify answers stay grounded in sources, citations resolve, follow-ups keep context

Finished 2026-10-02 against `spec-v0.4.md` §0: page restyled without
Tailwind (moved to `src/pages/AskPage.tsx`), retrieval switched to any-term
FTS (a question's words are never all in one article), installed-model
aware, follow-ups retrieve with the previous question's terms.

### Rest of v0.4 (full detail in `spec-v0.4.md`)

- [x] Ollama start prompt: `binaryInstalled` + `POST /api/ollama/start`
- [x] User-managed feeds: add (SSRF-gated, must parse) / rename / disable / move / delete (saved articles kept under Manual Links; deleted defaults stay deleted)
- [x] Search-link templates (Settings › Search Links, chips on /search)
- [x] Federated results: Hacker News via Algolia, server-side, degrades to local-only
- [x] Search filters (category, date range, saved-only), `<mark>` highlights, search-this-category box
- [x] Daily AI briefing: `/briefing`, 7 AM job, regenerate, cached per date
- [x] react-router 7.18 (0 prod audit findings)
- [x] Topics view actually groups (grouping was broken since the port)
- [x] Hourly weather observations + retention
- [x] Fixed: refresh aborting on fresh DBs (default-feed seeding), search results missing source/date/saved

---

## Known Issues & Technical Debt
- [ ] ThemeProvider React Fast Refresh warning (low priority)
- [ ] GitHub Actions security vulnerability (Dependabot flagged) — subsumed by the glib note below
- [ ] Backend code organization: consolidate feed fetching logic
- [ ] Dependabot finding in `glib 0.18.5`. The crate only enters the Cargo.lock because `webkit2gtk` is declared under `cfg(target_os = "linux")`; it is never compiled on the macOS build. Upstream fix requires `webkit2gtk` >= 0.20 (glib 0.20) — track on `webkit2gtk` release; no action possible until Tauri bumps its GTK stack.
