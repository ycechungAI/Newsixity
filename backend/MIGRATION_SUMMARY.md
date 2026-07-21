# FastAPI Backend Migration — Stages 0–6 Summary

**Project:** Newsixity (Node.js/Next.js → Python/FastAPI)  
**Status:** Stages 0–6: 100% complete (24/24 API endpoints live, security middleware in place)  
**Target completion:** Stage 7 (Opus), Stage 8–10 (Sonnet/Opus)  
**Deployed footprint:** On track for ~200–300 MB (no Node, no Chromium, pure Python)

---

## Completion Summary by Stage

### Stage 0: Scaffolding & Configuration ✅ (Opus 4.8)
- FastAPI app initialization with lifespan management
- SQLAlchemy 2.0 sync database setup (threadpool handlers)
- Configuration from environment (pydantic-settings)
- Database init hook on startup

### Stage 1a: Database Schema ✅ (Opus 4.8)
- 12 SQLAlchemy ORM models (Category, Feed, Article, ArticleGroup, ArticleResearch, SearchQuota, Setting, StockWatchlist, StockQuoteCache, StockChartCache, MarketHeatmapSnapshot, UserPreference)
- 14 indexes + WAL mode + foreign keys enabled + AUTOINCREMENT pragmas
- Verified column-for-column against production 109 MB SQLite database
- AUTOINCREMENT bug fixed (all 12 tables now properly flagged)

### Stage 1b: Repository Layer ✅ (Haiku + Sonnet review)
- 96 exported functions across 12 repository modules (~1,930 LOC port of queries.ts)
- Categories, Articles, Feeds, Article Groups, Stats, Article Research, Search Quota, Settings (with AES-256-GCM encryption), Finance (watchlist, quotes, charts, heatmaps), Console (queue management, culling), Ranking, Preferences
- 6 bugs found by Sonnet review + fixed (SQLAlchemy 1.x syntax, N+1 queries, SSRF bypass, etc.)
- Verified via read-only checks against production database

### Stage 2: Pydantic Schemas ✅ (Haiku 4.5)
- 30+ models for domain objects, requests, and responses (420 LOC port of types/index.ts)
- Field aliasing: camelCase (API) ↔ snake_case (internal/DB)
- Comprehensive validators: positive integers, URL validation, string bounds, numeric ranges
- All tested: validation catches invalid inputs correctly

### Stage 3: Utilities & Deduplication ✅ (Haiku 4.5)
- 8 utility modules: date formatting, search engine detection, video URL extraction, HTML sanitization, URL parsing
- 2 dedup modules: title normalization, bigram similarity (Dice coefficient), article grouping
- All utilities tested with real-world examples
- 600 LOC total, all stdlib (no external dependencies)

### Stage 4: External Integrations ✅ COMPLETE

**Haiku built:**
- RSS feed parsing via feedparser (160 LOC)
  - `fetch_feed()`, `fetch_all_feeds()` with concurrency=5
  - Image extraction chain (enclosures → media:content → media:thumbnail → img tags)
- HTTP-only content extraction (200 LOC)
  - trafilatura + regex fallback (no Playwright per spec)
  - SSRF protection: IPv4/IPv6 private range detection + DNS filtering
- Search result extraction via DuckDuckGo HTML (150 LOC)
  - Static HTML scraping (Google/Bing render with JS → unscrapable)

**Sonnet built:**
- yfinance integration (`lib/integrations/finance.py`) — quote/chart/search, blocking calls
  wrapped in `asyncio.to_thread`; verified error-handling degrades to empty results rather
  than raising when Yahoo's endpoints are unreachable
- Ollama integration (`lib/integrations/ollama.py`) — `AsyncClient`-based summarize/research/
  group-label calls, single-flight `asyncio.Lock` matching Node's enqueue/mutex behavior;
  verified live end-to-end against a real local Ollama instance (summarization round-trip
  confirmed working)
- Health endpoint now performs real Ollama availability + installed-model checks (previously
  a stub)

### Stage 5: API Routers ✅ COMPLETE (24/24)

**Haiku built (4 routers):**
1. **Health** (`/api/health`) — database, feeds, articles, ollama status
2. **Categories** (`/api/categories`) — all categories with article counts
3. **Articles** (`/api/articles/{id}`, `/manual`, `/mark-all-read`) — full CRUD + bulk ops
4. **Feeds** (`/api/feeds`, `/refresh`, `/weights`) — list, trigger refresh, update weights

**Sonnet built (10 routers + supporting lib modules):**
5. **Settings** (`/api/settings`) — encrypted API key + Ollama config
6. **Preferences** (`/api/preferences`) — keyword CRUD + rebuild trigger
   (`lib/ranking/preferences.py` — keyword extraction/scoring port)
7. **Finance** (`/api/finance/{quote,chart,heatmap,search,watchlist}`)
   (`lib/finance/sp500.py` — S&P 500 constituent list for the heatmap)
8. **Ollama** (`/api/ollama/models`) — installed models + suggestions
9. **Research** (`/api/research`, `/api/research/history`)
   (`lib/research/orchestrator.py`, `lib/research/search.py` — Brave Search API →
   DuckDuckGo HTML fallback, no Playwright per spec)
10. **Summarize** (`/api/summarize`) — single-article + batch resummarization
    (`lib/services/summarization.py`)
11. **Console** (`/api/console`, `/queue`, `/cull`, `/backup`, `/stop`,
    `/resummarize-failed`) — admin queue management, SQLite `VACUUM INTO` backups,
    dev-server restart (`lib/logger/console.py` — in-memory log capture via a
    `logging.Handler`, replacing Node's global console interceptor)

**Result:** 24/24 endpoints live in OpenAPI spec; smoke-tested against the real 47,273-article
production DB (health, settings, preferences, console, articles all returned correct live data).

### Stage 6: Auth, Rate-Limit & Middleware ✅ COMPLETE (Opus 4.8)

Ports `src/lib/server/{auth,rate-limit}.ts` and `src/proxy.ts` into
`backend/app/lib/server/`, preserving Node's exact security semantics.

**Auth** (`lib/server/auth.py`) — a global ASGI middleware (`app.main.api_access_middleware`)
runs `check_api_access` over every `/api/*` request except the public `/api/health`,
mirroring Next's middleware/proxy:
- **Loopback trust:** requests whose `Host` normalizes to `localhost`/`127.0.0.1`/`::1`
  are trusted without a token; if `x-forwarded-for` is present its first hop must be a
  loopback IP (IPv4, `::1`, or `::ffff:127.*`).
- **Token auth** (outside local mode): `NEWSIXITY_ADMIN_TOKEN` / `NEWSIXITY_API_TOKEN`
  compared via constant-time `hmac.compare_digest`; token read from `Authorization: Bearer`
  or `x-newsixity-token`. Admin paths (`/api/console`, `/api/settings`, `/api/feeds/refresh`,
  `/api/feeds/weights`, `/api/summarize`, `/api/preferences`) always require the admin token.
- **CSRF/origin:** mutating methods are rejected 403 on cross-site `sec-fetch-site` or on
  `Origin` host mismatch, regardless of how they later authenticate.

**Rate limiting** (`lib/server/rate_limit.py`) — a per-route fixed-window limiter attached as
`Depends(rate_limit(routeKey, limit, windowMs))` on each route, mirroring Node's per-handler
`enforceRateLimit` calls (30 rate-limited routes; `/api/{health,categories,summarize,ollama/models}`
intentionally unlimited, matching the Node source). In-process bucket store with the same
5,000-bucket cap + stale/oldest eviction as Node's `Map`. A `RateLimitExceeded` exception +
central handler reproduce Node's `{"error":"Rate limit exceeded","retryAfter":N}` body and
`Retry-After` header (FastAPI's `HTTPException` would otherwise nest the body under `detail`).

**Verified end-to-end** (FastAPI `TestClient`): local-mode allow/deny (including loopback vs
public `x-forwarded-for`), token-mode (admin vs api token, admin-path gating), mutating CSRF +
origin 403s, and rate-limit 429 parity (30 requests pass, #31 blocked with `retryAfter:600`).

---

## Statistics

| Metric | Value |
|--------|-------|
| Backend LOC (Stages 0–5) | ~9,500 |
| Repository functions | 96 |
| Pydantic schemas | 30+ |
| API endpoints (live) | 24 / 24 |
| Database tables | 12 |
| Database indexes | 14 |
| Utilities | 8 modules |
| Dedup modules | 2 modules |
| Tests (passing) | All imports, cold-start verified |
| Production parity | ✅ Schema + queries verified against 109 MB DB |
| AUTOINCREMENT bugs fixed | 6 (across 12 tables) |
| Linter violations | 0 (Python backend) |

---

## Quality Assurance

✅ **Schema verification:** All 12 models verified column-for-column against production DB  
✅ **Query equivalence:** Repository layer verified via read-only checks on production DB  
✅ **AUTOINCREMENT parity:** sqlite_autoincrement=True added to all 12 tables (matches Node's schema.ts)  
✅ **SSRF protection:** IPv4/IPv6 private ranges + DNS blocking implemented  
✅ **Encryption parity:** AES-256-GCM settings matching Node app's crypto.ts  
✅ **Validator coverage:** All request bodies validated (positive IDs, URL format, numeric bounds)  
✅ **Cold-start tested:** All modules import successfully; FastAPI app starts without errors  
✅ **No breaking changes:** All pre-existing Node code untouched  

---

## Handoff Summary

**Stage 6 (Opus) — DONE:**
- ✅ Auth middleware (loopback trust + token auth + CSRF/origin)
- ✅ Per-route fixed-window rate limiting (matching Node's routeKey/limit/window table)

**To Opus (Stage 7):**
- APScheduler integration for RSS refresh, summarization, backup jobs
- Concurrency guards (asyncio locks) — run-once-per-process, no pile-up

**To Sonnet/Opus (Stage 8–10):**
- Vite build + StaticFiles serving + SPA fallback route
- pytest test suite (basic, database, security)
- Multi-stage Docker build
- Old-vs-new parity sign-off

---

## Architectural Decisions

1. **Sync SQLAlchemy 2.0** (not async) — SQLite serializes writes anyway; direct port of Node's better-sqlite3
2. **No Playwright** (HTTP-only content extraction) — Drops ~300 MB; JS-heavy sites degrade to RSS snippet
3. **Pydantic field aliasing** — One source of truth (snake_case DB/internal), camelCase API input/output
4. **Repository layer as single source of truth** — All DB access via repository functions, no raw SQL in routers
5. **Stdlib-only utilities** (Stages 2–3) — No external deps except feedparser/trafilatura (Stage 4, needed for RSS/content)

---

## Git History

- **Commit 0b9dba4** — Stages 0–3: scaffolding, database, repository, schemas, utilities
- **Commit c6e4a9b** — Stage 4–5 (Haiku): RSS/content/search integrations, 4 routers
- **Commit b778bb6** — Working tree sync (deps, cache, DB state, tooling)
- **Commit 9341033** — Stage 4–5 (Sonnet): yfinance + Ollama integrations, remaining 10 routers,
  all 24/24 endpoints complete
- **(this commit)** — Stage 6 (Opus): auth + rate-limit middleware (`lib/server/{auth,rate_limit}.py`),
  global `/api/*` access gate, per-route rate-limit dependencies on 30 routes

---

## Next Immediate Action

**Opus:** Stage 7 — APScheduler background jobs (RSS refresh, summarization, backup) with
asyncio concurrency guards, replacing `src/lib/server/background-services.ts`. All 24 API
endpoints are operational and now gated by auth + rate limiting; Stage 7 is the last backend
gate before wiring the frontend build (Stage 8).

