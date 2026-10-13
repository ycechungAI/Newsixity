# Newsixity Developer Guide

## 1. Setup Instructions

### Prerequisites
- Node.js 24+ and npm (`.nvmrc` pins 24; 20 and 22 are no longer supported)
- Python 3.11+
- Ollama (required for summarization and deep research features)

### Install dependencies
```bash
npm install
python3 -m venv .venv
source .venv/bin/activate
pip install -e "./backend[integrations]"
```

### Install git hooks (auto-linter)
```bash
sh scripts/install-hooks.sh
```

This installs a pre-commit hook that runs ESLint automatically before every `git commit`.

### Run the app
```bash
./start.sh
```

This starts the FastAPI backend (`:8000`, auto-reload) and the Vite dev server
(`:5173`, which proxies `/api/*` to the backend) in parallel.

Frontend: `http://localhost:5173`
Backend + API docs: `http://localhost:8000/docs`

### Stop services
```bash
./stop.sh
```

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
provided via environment variables. See [deep-research.md](deep-research.md).

---

## 2. Project Structure Overview

Newsixity is a **FastAPI (Python) backend + Vite/React (TypeScript) frontend**.
In production the backend serves the built SPA (`dist/`) and the `/api/*`
surface from a single origin — there is no Node runtime at production time.

### Top-level
- `src/` — frontend application code (React, TypeScript)
- `backend/` — FastAPI backend, SQLAlchemy models, business logic
- `data/` — SQLite DB + backups (dev mode, git-ignored)
- `docs/` — project docs
- `src-tauri/` — Tauri desktop shell (macOS/Windows/Linux packaging)
- `start.sh`, `stop.sh` — local dev service scripts

### `backend/app`
| Concern | Location |
|---|---|
| SQLAlchemy models | `backend/app/db/models.py` |
| Query layer | `backend/app/db/repository/*.py` |
| Pydantic schemas | `backend/app/schemas.py` |
| HTTP routes | `backend/app/routers/*.py` |
| Router registration | `backend/app/main.py` |
| Scheduled jobs (RSS refresh, summarize, backup) | `backend/app/lib/scheduler/*.py` |
| DB bootstrap + seed | `backend/app/db/init_db.py` |
| Auth, rate limiting | `backend/app/lib/server/*.py` |
| RSS/podcast parsing, content extraction, integrations | `backend/app/lib/{integrations,podcast}/*.py` |
| Ranking (scoring/promotion/preferences) | `backend/app/lib/ranking/*.py` |
| Deep research orchestration | `backend/app/lib/research/*.py` |

### `src/`
- `src/pages/*.tsx` — one file per route (`HomePage`, `CategoryPage`, `PodcastsPage`, etc.)
- `src/components/*` — UI components by domain (`articles/`, `finance/`, `podcasts/`, `layout/`, `ui/`, `weather/`)
- `src/lib/*` — client-side utilities (date, sanitize, URL, video, article mark-read queue)
- `src/types/index.ts` — shared TypeScript interfaces, camelCase to match API responses
- `src/main.tsx` — React Router route table
- `src/app/globals.css` — the entire stylesheet (no component library — plain CSS with `var(--*)` design tokens, theme-aware via `.dark` / `prefers-color-scheme`)

### `backend/tests/`
- `backend/tests/basic/` — unit tests for utility functions (no I/O)
- `backend/tests/security/` — input hardening and API access control tests
- `backend/tests/database/` — schema and CRUD tests
- `backend/tests/integration/` — RSS fetch, static route serving

---

## 3. Command Reference

| Command | Description |
|---|---|
| `npm run dev` | Start Vite dev server only |
| `npm run build` | Production frontend build (emits `dist/`) |
| `npm run lint` | Run ESLint (check, no changes) |
| `npm run lint:fix` | Run ESLint and auto-fix issues |
| `sh scripts/install-hooks.sh` | Install git pre-commit lint hook |
| `.venv/bin/python -m pytest backend/tests` | Run the full backend test suite |
| `./start.sh` | Start backend (`:8000`) + frontend (`:5173`) together |
| `./stop.sh` | Stop both services |

---

## 4. Development Workflow

1. Start local services (`./start.sh`).
2. Frontend changes go in `src/`, using the `@/*` path alias (`@/` maps to `src/`).
3. Backend changes go in `backend/app/`. If you change the data model:
   - Update `backend/app/db/models.py`
   - Add/extend a repository function in `backend/app/db/repository/*.py`
   - Update the matching Pydantic schema in `backend/app/schemas.py`
   - **New indexes on existing tables** need an explicit `CREATE INDEX IF NOT EXISTS` in `init_db.py` — `Base.metadata.create_all()` only creates missing tables, it never alters existing ones (see the comment at the top of `init_db.py`).
4. If you add/modify API routes:
   - Create `backend/app/routers/<name>.py` with `router = APIRouter()`
   - Register it in `backend/app/main.py` with `prefix="/api"` and `tags=["<name>"]`
   - Routes inside the file should **not** repeat the `/api` prefix — it's added once at registration
5. Run quality checks before committing:
```bash
npm run lint:fix
.venv/bin/python -m pytest backend/tests
npx tsc --noEmit -p .
```
6. Run manual smoke checks in the browser:
   - Feed refresh, article open/save/read toggles
   - Console page (`/console`)
   - Settings page (`/settings`)
   - Podcasts, Finance, Weather pages

---

## 5. Auto-Linter & Code Quality

### ESLint configuration
ESLint is configured in `eslint.config.js` with TypeScript support.

### Commands
```bash
npm run lint         # check for issues (exit 1 if any errors)
npm run lint:fix     # auto-fix issues in place
```

### Pre-commit hook (recommended)
Install once after cloning:
```bash
sh scripts/install-hooks.sh
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
.venv/bin/python -m pytest backend/tests -q
```

### Test runner
Backend tests use **pytest**. There is no separate frontend test suite —
frontend correctness is checked via `npx tsc --noEmit` and manual/browser
verification.

### Test layout

```
backend/tests/
├── basic/         # utility and parsing unit tests
├── security/      # SSRF, XSS, auth, input-hardening tests
├── database/      # schema and CRUD tests
└── integration/   # RSS fetch, static route serving
```

---

## 7. Security Architecture

### API access control (`backend/app/lib/server/auth.py`)
- **Local requests** (host: `localhost`, `127.0.0.1`, `::1`, or a loopback `X-Forwarded-For`) are trusted without a token. This is what makes the desktop app (Tauri webview → loopback backend) work with zero token wiring.
- **Remote requests** require `NEWSIXITY_ADMIN_TOKEN` or `NEWSIXITY_API_TOKEN` (Bearer header or `X-Newsixity-Token`).
- **Admin paths** (`/api/console`, `/api/settings`, `/api/feeds/refresh`, `/api/feeds/weights`, `/api/summarize`, `/api/preferences`) require the admin token even when only an API token is configured.
- **CSRF**: mutating requests are blocked if `Sec-Fetch-Site: cross-site` or if `Origin` doesn't match `Host`.

### Rate limiting (`backend/app/lib/server/rate_limit.py`)
In-memory fixed-window limiter, applied per-route via `Depends(rate_limit(route_key, limit, window_ms))`.

### SSRF protection (`backend/app/lib/integrations/content.py`)
Server-side URL fetches (article content extraction, podcast feed
subscription) are validated with `parse_http_url()` (rejects non-http(s)
schemes and credential-bearing URLs) then `resolves_to_blocked_ip()`
(DNS-resolves the hostname and blocks private/loopback/link-local
addresses, failing closed on lookup failure). Reuse these two functions —
don't write new fetch logic — for any new endpoint that fetches a
user-supplied URL server-side.

### Input sanitization
- `strip_html` (`backend/app/lib/utils/sanitize.py`) strips HTML before storing/displaying user-facing content.
- `parse_http_url` (`backend/app/lib/utils/url.py`) rejects dangerous protocols and credential-bearing URLs.

---

## 8. Common Troubleshooting

### Port 5173 or 8000 already in use
```bash
lsof -ti:5173 | xargs kill -9
lsof -ti:8000 | xargs kill -9
```

### Ollama appears offline
```bash
ollama serve
curl http://localhost:11434
```
Then confirm host/model in `/settings`, or check `/api/health`.

### Articles not updating
- Trigger refresh from the UI (top bar) or `POST /api/feeds/refresh`
- Check `/api/health`
- Check logs in `/console`

### SQLite issues (corruption/lock/startup errors)
1. Stop the app.
2. Restore a backup (see [backup.md](backup.md)).
3. Restart the app.

### `.venv` points at a stale path
`start.sh` detects this automatically (the venv's activate script bakes in
an absolute path at creation time, so a renamed/moved repo folder breaks
it) and rebuilds `.venv`. If you're setting up manually instead, just
`rm -rf .venv` and recreate it.
