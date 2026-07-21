# Migration Spec: Node.js/Next.js → Python/FastAPI

> Status: **Planning** · Last updated: 2026-07-21
> Trackers: [todo.md](todo.md) (task checklist) · [Improvements.md](Improvements.md) (slimming/perf backlog)

## 1. Goal

Convert Newsixity from a Next.js 16 full-stack app to a **Python/FastAPI** backend
that serves a **pre-built static React SPA**, with the smallest possible deployed
footprint. Behavioral parity with the current app is required.

## 2. Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Frontend strategy | **Option C** — hybrid: FastAPI serves the built SPA via `StaticFiles` + SPA-fallback route | No Node in the runtime; smallest deployable artifact |
| Content extraction | **HTTP-only** — `httpx` + `trafilatura`, **no headless browser** | Drops ~300 MB Chromium; JS-heavy sites degrade to RSS snippet |
| DB access (Stage 0) | **Sync SQLAlchemy 2.0** (threadpool handlers + WAL + busy_timeout) | Mirrors better-sqlite3; SQLite serializes writes anyway; direct port of 1,930 LOC of queries |
| Build model | Node used **only at build time** (multi-stage Docker), never shipped | Keeps runtime pure-Python |
| Primary size target | Deployed image **~200–300 MB** | See [Improvements.md](Improvements.md) |

## 3. Current state (source of truth for scope)

- Next.js 16 + React 19 + TypeScript, ~13,083 LOC across ~119 `.ts/.tsx` files in `src/`.
- **Backend to port:** 24 API routes under `src/app/api/**` + all of `src/lib/**`
  (DB `queries.ts` alone is 1,930 LOC), plus `src/proxy.ts` middleware and `src/types`.
- **Frontend to preserve:** 9 pages + ~45 components under `src/app` and `src/components` (Tailwind).
- **Tests:** 10 test files, ~1,767 LOC (`tests/basic`, `tests/security`, `tests/database`).

## 4. Target architecture

```
┌─────────────────────────────────────────────┐
│  FastAPI (uvicorn)                            │
│   ├─ /api/*        → routers (ported handlers)│
│   ├─ StaticFiles   → built SPA (dist/)        │
│   ├─ catch-all     → index.html (SPA routing) │
│   ├─ lifespan      → APScheduler jobs         │
│   └─ SQLite (SQLAlchemy 2.0)                  │
└─────────────────────────────────────────────┘
   Build-time only: node → vite build → dist/
```

## 5. Dependency mapping

| Node package | Python replacement | Notes |
|---|---|---|
| `better-sqlite3` | `sqlite3` + **SQLAlchemy 2.0** | sync-vs-async decision → Stage 0 |
| `zod` | **pydantic v2** | 1:1 schema translation |
| `rss-parser` | **feedparser** | |
| `yahoo-finance2` | **yfinance** | pulls pandas/numpy (~70 MB) — heaviest dep |
| `ollama` (JS) | **ollama** (Python) / `httpx` | |
| `playwright-core` | **DROPPED** → `httpx` + `trafilatura` | per HTTP-only decision |
| Next.js API routes | **FastAPI routers** | |
| Next.js global-timer schedulers | **APScheduler** + `lifespan` + asyncio locks | concurrency model change |
| Next.js middleware (`proxy.ts`) | FastAPI middleware / dependency | |

## 6. Migration stages & model assignments

Model tiers (weakest → strongest):
- **Haiku 4.5** — mechanical, pattern-established, locally checkable. Bulk repetitive translation once conventions exist. Cheapest; never leads a stage whose conventions aren't set.
- **Sonnet 5** — mid-complexity judgment: API-shape adaptation, moderate logic, endpoint assembly, test ports, build wiring. Also the default **reviewer** for Haiku bulk output.
- **Opus 4.8** — highest stakes: architecture, concurrency/async, security, foundational DB design, parity sign-off. Anything where a subtle error corrupts data or opens a hole.

Rule: an Opus/Sonnet stage must fix conventions before Haiku parallelizes against them.

| # | Stage | Model | Notes |
|---|---|---|---|
| 0 | Architecture decisions & scaffolding | **Opus 4.8** | sync-vs-async DB, layout, config, lifespan skeleton — sets every convention |
| 1a | Schema + SQLAlchemy models | **Opus 4.8** | port `schema.ts` (192 LOC); pragmas/WAL/FK/indexes — DB foundation |
| 1b | Bulk query translation | **Haiku 4.5** (Sonnet 5 review) | `queries.ts` 1,930 LOC; Sonnet reviews dedup/cull/ranking queries |
| 2 | Pydantic schemas | **Haiku 4.5** | `types/index.ts` + ~18 zod files — 1:1 mapping |
| 3 | Pure business logic | **Haiku 4.5** (Sonnet 5 for ranking math) | dedup, ranking, utils, weather codes |
| 4 | External integrations | **Sonnet 5** (yfinance/ollama), **Haiku 4.5** (RSS/weather/HTTP fetcher) | Sonnet where API shapes differ |
| 5 | API endpoints (24 routers) | **Haiku 4.5** (Sonnet 5 review) | Sonnet reviews console/research/summarize (scheduler-touching) |
| 6 | Auth, rate-limit, middleware | **Opus 4.8** | `auth.ts` loopback trust, `rate-limit.ts` — security-critical |
| 7 | Background schedulers & concurrency | **Opus 4.8** | riskiest: setInterval singletons → APScheduler/asyncio |
| 8 | Frontend: Vite build + StaticFiles serve | **Sonnet 5** (design) / **Haiku 4.5** (wiring) | SPA fallback route, same-origin (no CORS) |
| 9 | Test port → pytest | **Haiku 4.5** (basic/db), **Sonnet 5** (security suite) | preserve intent of `tests/security` |
| 10 | Ops: multi-stage Docker, start/stop, parity | **Sonnet 5** (Docker/scripts), **Opus 4.8** (parity sign-off) | old-vs-new side-by-side validation |

## 7. Non-goals / out of scope

- No new features; parity only.
- No UI redesign (components preserved as-is, only their data source changes).
- Finance feature retained (accepts the pandas/numpy weight).
- JS-rendered-page scraping intentionally dropped (HTTP-only decision).

## 8. Success criteria

- All 24 endpoints respond with equivalent shapes to the current app.
- Summaries, dedup grouping, and rankings match the Node version on the same inputs.
- Background jobs (RSS refresh, summarization, backup) run once-per-process without pile-up.
- Deployed image ~200–300 MB; no Node/Chromium/`node_modules` in the runtime.
- pytest suites pass, including ported security tests.
