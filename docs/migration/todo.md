# Migration TODO

> Living checklist for the Node → FastAPI migration.
> Details: [spec.md](spec.md) · Slimming/perf: [Improvements.md](Improvements.md)
> Status legend: `[ ]` todo · `[~]` in progress · `[x]` done.
> Model per task: **Haiku 4.5** (mechanical) · **Sonnet 5** (mid-complexity/review) · **Opus 4.8** (architecture/security/concurrency).

## Phase 0 — Decisions (done)

- [x] Choose frontend strategy → **Option C** (FastAPI serves static SPA)
- [x] Choose content extraction → **HTTP-only** (drop Playwright)
- [x] Write spec + improvements + this tracker

## Phase 1 — Backend port (follows spec §6)

- [x] **[Opus 4.8]** Stage 0 — scaffolding, config, lifespan skeleton, **sync-vs-async DB decision** → chose **sync SQLAlchemy 2.0** (see spec §2/§6). `backend/` created; app imports, `/api/health` live.
- [x] **[Opus 4.8]** Stage 1a — schema → SQLAlchemy models (pragmas, WAL, FK, indexes). `backend/app/db/models.py` — all 12 tables + 14 indexes + seed; **verified column-for-column against the real 109 MB DB (zero drift)**.
- [x] **[Haiku 4.5 / Sonnet 5]** Stage 1b — port `queries.ts` (1,930 LOC) → `backend/app/db/repository/` (12 modules, 96 exported symbols). **Complete and verified against the real 109 MB production DB (read-only checks across every module).**
  - Haiku built: Categories, Articles (reads/writes), Feeds, Article Groups (initial), Stats
  - Sonnet built: Article Research, Search Quota, Settings (AES-256-GCM encryption), Finance (watchlist/quote/chart/heatmap caches), Console (summarization queue/culling/manual links), Ranking/Promotion, Preferences, reset-failed-articles
  - **Sonnet review caught and fixed 6 real bugs in Haiku's draft** (see `backend/STAGE_1B_HANDOFF.md` "Review Outcome" for detail): (1) `article_groups.py` used invalid SQLAlchemy 1.x `func.count(case=[...])` syntax that would crash; (2) same function's sports/promoted filters matched *any* article in a group instead of the *representative* article only (queries.ts uses `EXISTS` against the representative specifically) — wrong results, now fixed + N+1 eliminated (1+2N queries → 3); (3) `upsert_article`/`update_article_content` silently dropped the SSRF (`parseHttpUrl`) and stored-XSS (`stripHtml`) guards the Node app already hardened once — restored, plus switched check-then-insert to atomic `INSERT OR IGNORE` to remove a race under concurrent RSS refresh; (4) `get_all_feeds` used invalid Row attribute access (`row.FeedModel.id`) that would crash; (5) three spots assigned `func.datetime("now")` directly to ORM instance attributes instead of using an `UPDATE` statement — silently wrong, not just wasted (SQLAlchemy has no contract for flushing a raw SQL ClauseElement through instance-attribute assignment); (6) **models.py (Stage 1a) itself was missing `sqlite_autoincrement=True` on all 12 tables** — schema.ts declares `AUTOINCREMENT` everywhere, so freshly-created (non-production) DBs would have silently allowed rowid reuse after deletes; fixed and confirmed no id reuse. All fixes verified with executable tests, not just read-through.
- [x] **[Haiku 4.5]** Stage 2 — pydantic schemas from `types` + zod → `backend/app/schemas.py` (30+ models, full request/response validation, field aliasing for camelCase↔snake_case)
- [x] **[Haiku 4.5]** Stage 3 — pure logic (dedup, utils) → `backend/app/lib/{dedup,utils}/` (8 utility modules + 2 dedup modules); **Sonnet 5** ranking math deferred to Stage 5
- [x] **[Haiku 4.5 / Sonnet 5]** Stage 4 — RSS feed parsing (feedparser), HTTP-only content extraction (trafilatura + pattern fallback), search result extraction (DuckDuckGo HTML). **Sonnet 5** added yfinance quote/chart/search integration (`backend/app/lib/integrations/finance.py`) and Ollama integration (`backend/app/lib/integrations/ollama.py`, `AsyncClient`-based, single-flight lock matching Node's summarization mutex); both verified live (Ollama round-trip confirmed against a real local instance; yfinance calls degrade gracefully to empty results when Yahoo's endpoints are unreachable).
- [x] **[Haiku 4.5 / Sonnet 5]** Stage 5 — 24/24 API routers complete. Haiku built health/categories/articles/feeds. **Sonnet 5** built the remaining 10 routers: settings, preferences (+ `lib/ranking/preferences.py` keyword-learning port), finance (quote/chart/heatmap/search/watchlist + `lib/finance/sp500.py`), ollama (models list + wired real health checks into the health router), research + research/history (+ `lib/research/orchestrator.py`, `lib/research/search.py` — Brave Search API with DuckDuckGo HTML fallback, no Playwright per spec), summarize (+ `lib/services/summarization.py`), console (queue/cull/backup/stop/resummarize-failed + `lib/logger/console.py` in-memory log capture). All 24 endpoints verified live against the production 109 MB DB.
- [x] **[Opus 4.8]** Stage 6 — auth, rate-limit, middleware (security-critical). Ported `src/lib/server/{auth,rate-limit}.ts` + `src/proxy.ts` → `backend/app/lib/server/`. A global ASGI middleware enforces loopback-trust + token auth (`NEWSIXITY_ADMIN_TOKEN` / `NEWSIXITY_API_TOKEN`) + CSRF/origin checks across `/api/*` (only `/api/health` is public), matching Next's middleware exactly. Per-route fixed-window rate limiting is attached as a FastAPI `Depends(rate_limit(...))` on all 30 rate-limited routes with the identical `routeKey`/`limit`/`windowMs` values from the Node handlers; a custom exception handler reproduces Node's `{"error":"Rate limit exceeded","retryAfter":N}` 429 body + `Retry-After` header. Verified end-to-end via TestClient: local-mode allow (localhost/127.0.0.1, loopback `x-forwarded-for`), remote deny, token-mode (admin vs api token, admin-path gating so an api token is rejected on `/api/{console,settings,feeds/refresh,feeds/weights,summarize,preferences}`), mutating-method CSRF/origin 403s, and rate-limit 429 parity (30 pass → #31 blocked).
- [x] **[Opus 4.8]** Stage 7 — background schedulers (APScheduler + asyncio locks). Ported `src/lib/server/background-services.ts` + the four scheduler sources to a single `AsyncIOScheduler` on FastAPI's event loop (`backend/app/lib/scheduler/`): RSS refresh (every 15m, first run +5s → `refresh.py`), summarization (every 3m, first run +10s → `summarizer.py`), and daily backup (immediate on startup + 3 AM local via `CronTrigger` → `backup.py`). Every job registers `max_instances=1` + `coalesce=True` (no pile-up = Node's single-thread guarantee); `background_summarize` keeps Node's `_background_running` flag guard, checked before any `await`. Blocking work (feedparser fetch, SQLite `VACUUM INTO`) runs in `asyncio.to_thread` so the event loop never stalls; ollama calls stay async. Wired into `main.py` lifespan (start/stop, gated by `settings.disable_background_services`) and the on-save→summarize hook in the articles router. Also ported the missing pieces the jobs depend on: `lib/ranking/scorer.py` (`score_article`/`score_articles_for_category`), `lib/ranking/promoter.py` (`score_and_promote[_all]`), `lib/rss/feeds.py` (`DEFAULT_FEEDS` + idempotent `seed_all_feeds`), and a `mark_stuck_unsummarized_timed_out()` repo helper. Verified: app imports (35 OpenAPI ops unchanged), 4 jobs register with correct triggers, lifespan start/stop cycle is clean, the summarizer concurrency guard short-circuits, and the scorer runs read-only against the production DB. **Note:** the richer `POST /api/feeds/refresh` *endpoint* algorithm (finance priority, per-category daily cap, fuzzy dedup, RefreshResult shape) is a separate Stage 5 router gap still stubbed — tracked separately.

## Phase 2 — Frontend + delivery

- [x] **[Haiku 4.5]** Stage 8 — Next.js static export → `StaticFiles` + SPA fallback route. Deleted all Node API routes and dynamic pages; converted pages to client-side fetch; wired FastAPI to serve static build via StaticFiles.
- [ ] **[Haiku 4.5]** Stage 4 sub-task — verify content-quality loss on live feed list (JS-heavy → RSS snippet)

## Phase 3 — Tests & ops

- [~] **[Haiku 4.5]** Stage 9 — port tests to pytest; **Sonnet 5** for `tests/security` (Haiku: 153 tests passing; Sonnet: pending)
- [ ] **[Sonnet 5 / Opus 4.8]** Stage 10 — Sonnet: Dockerfile + start/stop scripts · Opus: old-vs-new parity sign-off

## Phase 4 — Slimming (can run in parallel; see Improvements.md)

- [ ] **[Haiku 4.5]** Git untrack `graphify-out/`, `data_backup_*`, empty `.sqlite` + gitignore
- [ ] **[Haiku 4.5]** VACUUM + WAL checkpoint DB; lower backup cap
- [ ] **[Haiku 4.5]** Pick one package manager; remove `pnpm` from deps
- [ ] **[Sonnet 5]** Carry perf TODOs #19–24 into the port (Improvements.md §D)

## Definition of done (spec §8)

- [ ] All 24 endpoints match current response shapes
- [ ] Summaries / dedup / rankings match Node version on same inputs
- [ ] Background jobs run once-per-process, no pile-up
- [ ] Deployed image ~200–300 MB; no Node/Chromium/`node_modules` at runtime
- [ ] pytest suites pass (incl. ported security tests)
