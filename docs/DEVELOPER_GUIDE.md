# Newsixity Developer Guide

## 1. Setup Instructions

### Prerequisites
- Node.js 20+ and npm
- Ollama (required for summarization and deep research features)
- SQLite is bundled via `better-sqlite3` (no separate install required)

### Install dependencies
```bash
npm install
```

### Install git hooks (auto-linter)
```bash
npm run hooks:install
```

This installs a pre-commit hook that runs ESLint automatically before every `git commit`.

### Run the app
Option A (recommended for full local behavior):
```bash
./start.sh
```

Option B (manual):
```bash
ollama serve
npm run dev
```

App URL: `http://localhost:3000`

### Optional Deep Research setup
Use the Settings page (`/settings`) and configure:
- `Brave Search API Key`
- `Ollama Model`
- `Ollama Host` (default: `http://localhost:11434`)

You can also set:
```bash
export BRAVE_SEARCH_API_KEY="your-key"
export NEWSIXITY_SETTINGS_ENCRYPTION_KEY="long-random-secret"
```

`NEWSIXITY_SETTINGS_ENCRYPTION_KEY` is required to persist sensitive settings
(e.g. `brave_search_api_key`) in SQLite. Without it, API keys must be
provided via environment variables.

### Stop services
```bash
./stop.sh
```

---

## 2. Project Structure Overview

### Top-level
- `src/` — application code
- `tests/` — automated test suites
- `scripts/` — developer tooling (git hook installer)
- `data/` — SQLite DB + backups (git-ignored)
- `docs/` — project docs and plans
- `start.sh`, `stop.sh` — local service scripts

### `src/app`
- App Router pages (`page.tsx`, category/article/saved/settings/console pages)
- API routes under `src/app/api/*`

### `src/components`
UI components by domain:
- `articles/` — feed, cards, groups, research modal, search results
- `finance/` — dashboard, charts, heatmap, watchlist
- `weather/` — current conditions, forecast
- `layout/` — header, sidebar, topbar
- `ui/` — shared primitives (modals, pagination, toggles)

### `src/lib`
- `db/` — SQLite connection, schema, query functions
- `rss/` — feed definitions, fetching, scheduling
- `ollama/` — summarization/research clients + background scheduler
- `research/` — web search and orchestration
- `ranking/` — scoring, promotion, preference learning
- `content/` — article content extraction (HTTP + headless Chromium fallback)
- `dedup/` — bigram-similarity duplicate detection
- `backup/` — DB backup scheduler
- `finance/`, `weather/` — external data integrations
- `server/` — auth, rate limiting, request parsing, response helpers
- `utils/` — date, sanitize, URL, video, search utilities
- `logger/` — console/log utilities

### `src/types`
Shared TypeScript interfaces used across UI, API, and services.

### `tests/`
- `tests/basic/` — unit tests for utility functions (no I/O)
- `tests/security/` — input hardening and API access control tests
- `tests/database/` — schema and CRUD tests using isolated in-memory SQLite
- `tests/setup/loader.mjs` — ESM loader for `next/server` resolution in test environment

---

## 3. npm Scripts Reference

| Script | Description |
|---|---|
| `npm run dev` | Start Next.js dev server |
| `npm run build` | Production build |
| `npm run start` | Serve production build |
| `npm run lint` | Run ESLint (check, no changes) |
| `npm run lint:fix` | Run ESLint and auto-fix issues |
| `npm run hooks:install` | Install git pre-commit lint hook |
| `npm run tests` | Run lint + all test suites |
| `npm run test:basic` | Utility and parsing unit tests |
| `npm run test:security` | Input hardening and auth tests |
| `npm run test:db` | Schema and CRUD tests (in-memory DB) |
| `npm run audit` | npm security audit (all deps) |
| `npm run audit:prod` | npm security audit (prod deps only) |

---

## 4. Development Workflow

1. Start local services (`./start.sh` or `ollama serve` + `npm run dev`).
2. Make changes in `src/` using the `@/*` path alias (`@/` maps to `src/`).
3. If you change the data model:
   - Update `src/lib/db/schema.ts` (schema/migrations — use `ALTER TABLE … ADD COLUMN IF NOT EXISTS` pattern)
   - Update `src/lib/db/queries.ts`
   - Update related `src/types/index.ts`
4. If you add/modify API routes:
   - Call `checkApiAccess(request)` at the top of the handler
   - Validate inputs with Zod and `parseJsonBody`/`parseOptionalJsonBody`
   - Return consistent status codes using helpers in `src/lib/server/api-response.ts`
5. Run quality checks before committing:
```bash
npm run lint:fix   # fix any lint issues
npm run tests      # lint + all 222 tests
npm run build      # confirm TypeScript compiles
```
6. Run manual smoke checks in the browser:
   - Feed refresh
   - Article open/save/read toggles
   - Console page (`/console`)
   - Settings page (`/settings`)
   - Finance and weather pages

---

## 5. Auto-Linter & Code Quality

### ESLint configuration
ESLint is configured in `eslint.config.mjs` using `eslint-config-next` with TypeScript support.

### Commands
```bash
npm run lint         # check for issues (exit 1 if any errors)
npm run lint:fix     # auto-fix issues in place
```

### Pre-commit hook (recommended)
Install once after cloning:
```bash
npm run hooks:install
```

The hook runs `npm run lint` before every commit. If there are lint errors, the commit is blocked.
To bypass in an emergency:
```bash
git commit --no-verify -m "message"
```

---

## 6. Testing

### Running tests
```bash
npm run tests          # full pipeline: lint + test:basic + test:security + test:db
npm run test:basic     # utility and parsing unit tests (129 tests)
npm run test:security  # input hardening and auth tests (54 tests)
npm run test:db        # schema and CRUD tests (39 tests, in-memory SQLite)
```

### Test runner
Tests use **Node.js's built-in `node --test` runner** with `--experimental-strip-types` for native TypeScript support. No extra testing framework (Jest, Vitest, etc.) is needed.

### Test layout

```
tests/
├── basic/
│   ├── sanitize.test.ts    # stripHtml, truncate, extractImageFromHtml
│   ├── date.test.ts        # timeAgo, formatDate
│   ├── video.test.ts       # extractVideoInfo, isVideoUrl (all platforms)
│   ├── similarity.test.ts  # normalizeTitleForHash, bigramSimilarity, isDuplicate
│   ├── url.test.ts         # parseHttpUrl, isHttpUrl
│   └── search.test.ts      # detectSearchEngine, isSearchEngineUrl
├── security/
│   ├── auth.test.ts        # checkApiAccess: local trust, CSRF, tokens, admin paths
│   └── input.test.ts       # XSS, protocol enforcement, credential injection, SSRF
├── database/
│   ├── schema.test.ts      # initializeSchema: tables, seeds, migrations, idempotency
│   └── crud.test.ts        # CRUD: constraints, foreign keys, defaults, read/write
└── setup/
    └── loader.mjs          # ESM hook: maps next/server → next/server.js for tests
```

### Writing new tests
- Import source modules using **relative paths** (e.g. `../../src/lib/utils/sanitize.ts`) — `@/` aliases are not resolved by Node's test runner.
- For tests that import from `next/server`, add `--import ./tests/setup/loader.mjs` to the test command.
- Database tests should use an **in-memory SQLite database** (`new Database(':memory:')`) — never the real `data/newsixity.db`.

---

## 7. Security Architecture

### API access control (`src/lib/server/auth.ts`)
- **Local requests** (host: `localhost`, `127.0.0.1`, `::1`) are trusted without a token.
- **Remote requests** require a `NEWSIXITY_API_TOKEN` or `NEWSIXITY_ADMIN_TOKEN` (Bearer header or `X-Newsixity-Token` header).
- **Admin paths** (`/api/console`, `/api/settings`, `/api/feeds/refresh`, `/api/feeds/weights`, `/api/summarize`, `/api/preferences`) require the admin token even when an API token is configured.
- **CSRF**: mutating requests (POST/PUT/DELETE) are blocked if `Sec-Fetch-Site: cross-site` or if the `Origin` header doesn't match the `Host`.

### Rate limiting (`src/lib/server/rate-limit.ts`)
In-memory token-bucket limiter. Apply to expensive endpoints with `enforceRateLimit(request, { routeKey, limit, windowMs })`.

### SSRF protection (`src/lib/content/fetcher.ts`)
All outbound URL fetches are validated via `parseHttpUrl` (rejects non-HTTP, credentials) then checked against a private-IP blocklist before the HTTP request is issued.

### Input sanitization
- `stripHtml` in `src/lib/utils/sanitize.ts` strips all HTML tags before storing or displaying user-facing content.
- `parseHttpUrl` in `src/lib/utils/url.ts` rejects dangerous protocols (`javascript:`, `file://`, etc.) and credential-bearing URLs.

---

## 8. Common Troubleshooting

### Port 3000 already in use
```bash
lsof -ti:3000 | xargs kill -9
```

### Ollama appears offline
```bash
ollama serve
curl http://localhost:11434
```
Then confirm host/model in `/settings`.

### Articles not updating
- Trigger refresh from the UI (top bar) or `POST /api/feeds/refresh`
- Check `/api/health`
- Check logs in `/console`

### SQLite issues (corruption/lock/startup errors)
1. Stop the app.
2. Restore a backup from `data/backups/`:
```bash
cp data/newsixity.db data/newsixity.db.old
cp data/backups/<backup-file>.db data/newsixity.db
```
3. Restart the app.

### Native module issues after Node upgrade (`better-sqlite3`)
```bash
rm -rf node_modules package-lock.json
npm install
```

### Browser-based extraction fails
Ensure Chromium is available for `playwright-core`:
```bash
npx playwright-core install chromium
```
Prefer configuring Brave Search API in `/settings` for research reliability.

### Lint errors in tests
If you add new test files and lint complains, make sure:
- Unused imports are removed
- Variables are typed or use `as never` for duck-typed mock arguments
- Run `npm run lint:fix` to auto-resolve most issues
