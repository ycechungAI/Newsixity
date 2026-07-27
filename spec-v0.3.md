# Newsixity v0.3 — Implementation Spec

Companion to the approved plan at `~/.claude/plans/polished-sprouting-snowglobe.md`.
That file is the *what*; this file is the *how*, plus every trap this codebase has
already sprung on us. Written by Opus 5 for Sonnet 5 sessions that start cold.

**Read sections 0–3 before writing any code.** They are where the bugs come from.
Sections 4+ are per-task and can be read on demand.

Everything here was verified against the working tree on 2026-07-27. Symbol names
are stable; line numbers drift — re-grep rather than trusting a number.

---

## 0. Ground rules

1. **Verify before you "fix".** Twice in this project a confident bug report turned
   out to be a testing artifact (see §3.6). Reproduce with a measurement that
   cannot lie before changing code. If you can't reproduce it, say so.
2. **Trust code over docs.** Several root-level docs were confidently wrong (one
   described a deletion-based ranking design that was never shipped). Read the
   implementation.
3. **Never report done with failing tests.** State failures with output.
4. **Stay in your lane.** When several agents run at once, only touch the files
   your task owns. Shared files (`models.py`, `init_db.py`, `main.py`,
   `repository/__init__.py`, `globals.css`, `Sidebar.tsx`, `main.tsx`) are
   collision points — that's why work is sequenced in waves.
5. **Match surrounding style.** Comment density, naming, and idiom. Comments
   should explain *why*, especially non-obvious constraints — not narrate *what*.
6. **No new dependencies** without saying so explicitly in your report. Every new
   Python dep means a PyInstaller respin and a bigger desktop bundle.

---

## 1. Environment

```bash
# Backend — ALWAYS this interpreter. `source .venv/bin/activate` does NOT
# persist between separate bash tool calls; a bare `python`/`pytest` picks up
# system Python and dies on missing numpy/pandas.
.venv/bin/python -m pytest backend/tests -q

# Frontend
npm run lint          # must be clean except ONE known ThemeProvider warning
npm run build         # must succeed
npx tsc --noEmit      # has PRE-EXISTING errors, see below — not your problem
```

**Baselines as of 2026-07-27** (wave 1 agents are adding more):
- `pytest backend/tests` → **261 passed**
- `npm run lint` → 0 errors, 1 warning (`ThemeProvider.tsx` Fast Refresh) — this
  one is pre-existing and acceptable. **Do not add new ones** (see §3.5).
- `npx tsc --noEmit` → pre-existing errors in `src/pages/ConsolePage.tsx` (octal
  escape, `below_threshold`) and in the root `tests/` directory (dead Next.js-era
  suite referencing `better-sqlite3` and `src/lib/db/schema.ts`, neither of which
  exists any more). **These are not regressions.** Confirm with `git status` that
  you didn't touch the file before assuming a tsc error is yours.

Run the dev stack with `./start.sh` (backend :8000, Vite :5173). To run just the
backend: `cd backend && ../.venv/bin/python -m uvicorn app.main:app --port 8000`.

---

## 2. Architecture as it actually is

Ported from Next.js to **FastAPI + Vite/React**. Ignore any doc mentioning
`src/app/api/*`, `src/lib/db/*`, or `better-sqlite3` — those paths are gone.

| Concern | Location |
|---|---|
| Routers | `backend/app/routers/*.py` |
| DB models | `backend/app/db/models.py` |
| Queries | `backend/app/db/repository/*.py` |
| Engine/session | `backend/app/db/session.py` |
| Schema creation | `backend/app/db/init_db.py` |
| External fetches | `backend/app/lib/integrations/`, `lib/podcast/`, `lib/utils/video.py` |
| Background jobs | `backend/app/lib/scheduler/service.py` |
| Auth | `backend/app/lib/server/auth.py` |
| Pages | `src/pages/*.tsx` |
| Components | `src/components/**` |
| Styles | `src/app/globals.css` (single stylesheet, CSS custom properties) |

**Desktop packaging:** a Tauri Rust shell spawns the PyInstaller-frozen backend on
a loopback port and points a webview at it. Rebuild with `npm run build:mac`.

---

## 3. Invariants — this is where the bugs come from

Each item below is a bug that actually shipped or was caught late in this project.

### 3.1 Backend / FastAPI

- **Never repeat `/api` in a route path.** Routers are registered with
  `app.include_router(x.router, prefix="/api")`. Declaring `@router.get("/api/podcasts")`
  produced `/api/api/podcasts` and made all 7 podcast routes unreachable.
- **A bare scalar parameter is a QUERY parameter, not a JSON body.**
  `def f(is_favorite: bool)` reads `?is_favorite=`. To accept JSON use `body: dict`
  (the established convention here) or a Pydantic model.
- **Pydantic `validation_alias` means the attribute is the camelCase name.**
  With `feedUrl: str = Field(validation_alias="feed_url")`, the Python attribute is
  `payload.feedUrl`. `payload.feed_url` raises `AttributeError`.
- **Call `session.refresh(obj)` after `commit()` before returning an ORM object.**
  `commit()` expires attributes and the session closes before FastAPI serialises,
  giving `DetachedInstanceError`. This bit three podcast endpoints at once.
- **No blocking I/O in an `async def` handler** — it blocks the whole event loop.
  Wrap in `asyncio.to_thread` (`lib/scheduler/backup.py` does this correctly;
  `routers/console.py::create_backup` still does not — a known open item).
- **Error body shapes differ.** Middleware and the rate limiter emit
  `{"error": ...}`; `raise HTTPException(...)` emits `{"detail": ...}`. The Console
  UI reads `data.error`. Check what the specific consumer expects — don't assume.
- **Admin auth is path-prefix based, not a dependency.** `ADMIN_PATH_PREFIXES` in
  `lib/server/auth.py` gates `/api/console`, `/api/settings`, etc. in middleware.
  A new admin route gets protection *only* by living under one of those prefixes.
  Loopback requests are trusted without a token (this is what makes the desktop
  app work without provisioning secrets).
- **Prefer batch queries.** Several N+1s were deliberately fixed here
  (`get_articles_by_ids`, `get_cached_quotes`, `mark_articles_read`). Don't
  reintroduce per-row loops.

### 3.2 Database

- **There is no Alembic.** Schema comes from `Base.metadata.create_all()` in
  `init_db.py`. That creates *missing tables* only — it will **not** alter an
  existing table. Adding an index to an existing table requires an explicit
  `CREATE INDEX IF NOT EXISTS` line in `init_db.py` (there's already one for
  `idx_articles_is_read_published`). Brand-new tables need nothing.
- **`init_db()` runs on every startup against the live production DB.** Everything
  must be idempotent.
- **WAL mode means the database is three files**: `.db`, `.db-wal`, `.db-shm`.
  Replacing the `.db` while a stale `-wal` exists corrupts or rewinds state. Any
  file-level swap must remove/checkpoint the sidecars.
- **`engine` and `SessionLocal` are module-level singletons created at import**
  and imported *by value* elsewhere (`db/__init__.py`, `init_db.py`). Rebinding
  `app.db.session.engine` at runtime will NOT update those aliases. To swap the
  underlying file, keep the same path and `engine.dispose()` — or do the swap
  before the engine is ever built.
- Timestamps: reuse `_js_iso_string()` from `repository/finance.py` (millisecond
  precision + literal `Z`, byte-compatible with the old Node app).
- Upserts: `sqlite_insert(...).on_conflict_do_update(...)` — see `finance.py`.

### 3.3 Outbound network — SSRF and CORS

- **Every outbound fetch goes through the guard**: `parse_http_url()`
  (`lib/utils/url.py`) then `resolves_to_blocked_ip()`
  (`lib/integrations/content.py`). Canonical example:
  `lib/podcast/parser.py::fetch_podcast_feed`. Copy that shape.
- If a URL is built from user input, **validate the input against a strict regex
  before interpolating it** (see `PLAYLIST_ID_RE` in `lib/utils/video.py`) so a
  crafted value can't inject query parameters or path segments.
- **`resolves_to_blocked_ip()` had a bug that blocked every hostname** because
  `is_blocked_ip()` fails closed on non-IP strings. Fixed by explicitly testing
  `ip_address()` parseability first. It has regression tests now — don't undo it.
- **The browser cannot fetch third-party APIs directly.** The Vite proxy only
  covers `/api`. `youtube.com` sends no `Access-Control-Allow-Origin`, so the old
  client-side playlist fetch was blocked in every browser and its `catch`
  silently returned an empty list — the feature looked "limited" but was dead.
  **Weather is the remaining offender**: `src/lib/weather/api.ts` calls
  Open-Meteo straight from the browser. Any new third-party call belongs behind
  an `/api/*` route (see `routers/finance.py` for the cache-aside pattern).

### 3.4 Scheduler

`lib/scheduler/service.py` holds one module-level `AsyncIOScheduler` behind an
idempotent `_started` flag. House rules, applied to every job: an explicit `id=`,
`max_instances=1`, `coalesce=True`. Three registration styles already exist
(interval with delayed first run; daily cron; one-shot at startup) — copy one.

### 3.5 Frontend

- **There is no MUI, no Tailwind, no component library, and no state library.**
  Dependencies are exactly: react, react-dom, react-router-dom. An earlier
  podcast implementation imported `@mui/material` and was completely
  build-broken. Use plain elements plus classes in `globals.css`.
- **Style only with existing CSS custom properties** (`var(--bg)`, `var(--fg)`,
  `var(--accent)`, `var(--border)`, `var(--panel)`, `var(--subtle)`). No
  hardcoded colours — the app has a light/dark toggle.
- **Don't export hooks or constants from a file that exports a component** —
  the `react-refresh/only-export-components` lint rule fires. Put shared hooks in
  a plain `.ts` module (e.g. `src/lib/video/playerContext.ts`).
- **Moving an `<iframe>` in the DOM reloads it.** The shared video player exists
  precisely to avoid that: it is mounted once above the router and positions
  itself over a placeholder using `position: fixed`, so docking/undocking is a
  CSS change only. Don't "simplify" it by re-parenting.
- **A percentage `padding-bottom` resolves against the PARENT's width**, so the
  classic 56.25% aspect-ratio hack breaks the moment the element's own width
  isn't the parent's. Use `aspect-ratio: 16 / 9`.
- `.article-card` has `overflow: hidden` — it clips anything drawn inside it.

### 3.6 Verification traps (these cost real time)

- **A hidden/backgrounded tab has rendering fully throttled.** `requestAnimationFrame`
  stops and **`ResizeObserver` never fires — not even its guaranteed initial
  callback**. Anything that looks like "the layout isn't updating" may be this.
  Check `document.visibilityState` and count rAF frames before believing it.
  Corollary: don't make correctness depend solely on `ResizeObserver`; drive
  updates from explicit React dependencies where you can.
- **Don't click by screenshot pixel coordinates** when a layout can shift; that
  produced a phantom "progress reset to 0" bug during the podcast work. Use
  `document.querySelector(...).click()`.
- **`read_network_requests` timestamps are too coarse** to prove sub-second
  timing. Use `performance.getEntriesByType('resource')`.
- To prove a DOM node *survived* an operation rather than being recreated, tag it
  (`el.dataset.probe = 'x'`) and re-check the tag afterwards.

### 3.7 Desktop app (Tauri) — constrains frontend choices

- The webview loads `WebviewUrl::External("http://127.0.0.1:<dynamic port>")`, so
  **`window.__TAURI__` is not available** — no Tauri IPC without adding
  `withGlobalTauri` plus a wildcard remote capability. Design around it.
- macOS Tauri uses **WKWebView (WebKit)**. So:
  - `documentPictureInPicture` — **not available** (Chromium-only). Always
    feature-probe and fall back.
  - Native `<video>` PiP — available.
- The frozen backend links **system** SQLite (`/usr/lib/libsqlite3.dylib`,
  3.51.0, FTS5 enabled), not the venv's.
- `_copy_seed_db_if_first_run()` only seeds when no DB exists, so rebuilding the
  app never touches the user's data in
  `~/Library/Application Support/Newsixity/`. **Keep it that way** — the user has
  explicitly asked that macOS builds preserve their existing database.

---

## 4. Wave 1 — LANDED. Do not redo; do not regress.

| Task | Owns | State |
|---|---|---|
| B-backend | `routers/console.py`, `db/session.py`, new `lib/backup/` | done + export/download added |
| D (FTS5) | `db/init_db.py`, `repository/articles.py` | done, **but unreachable — see below** |
| C-models | `db/models.py`, new `repository/weather.py`, `repository/__init__.py` | done |

### 4.1 Bugs found reviewing wave 1 — each now has a regression test

All three shipped passing tests and still had a real defect. The tests passed
because each picked inputs that could not expose the bug. Assume the same of
your own tests: pick the input that *would* fail if you were wrong.

1. **Timestamp-format mismatch in retention** (`repository/weather.py`).
   `observed_at` holds JS-ISO (`2026-06-27T06:23:05.530Z`); the cutoff was
   built with SQLite `datetime()` (`2026-06-27 06:23:05`). Comparing those is
   a *string* compare, and `T` (0x54) sorts above the space (0x20) — so no row
   from the cutoff day was ever deleted, at any time of day. Build cutoffs with
   `strftime('%Y-%m-%dT%H:%M:%fZ', ...)` to match the stored format. The
   original test used a 45-day-old row, which passes either way.
   Guard: `test_retention_deletes_rows_landing_on_the_cutoff_day`.

2. **Safety copy lost WAL data** (`lib/backup/restore.py`). The pre-restore
   safety copy used `shutil.copy2`, which copies only `newsixity.db` — but the
   DB is in WAL mode, so committed-and-not-yet-checkpointed rows live in
   `-wal`, which `apply_pending_restore` deletes moments later. Measured on a
   force-quit simulation: the copy contained **no tables at all** (4 KB main
   file, 12 KB WAL). Use `VACUUM INTO`, as `POST /api/console/backup` already
   does. Never `shutil.copy2` a live SQLite DB.
   Guard: `test_safety_copy_preserves_data_still_in_the_wal`.

3. **Safety copy was prunable** (`lib/backup/restore.py`). It was named
   `newsixity-pre-restore-*`, and `_cleanup_old_backups()` prunes everything
   matching `newsixity-` down to `MAX_BACKUPS` (2) — so two manual backups
   would delete the only file that can undo a bad restore. It is now
   `pre-restore-*` (`SAFETY_PREFIX`, deliberately not under `BACKUP_PREFIX`).
   Guard: `test_safety_copy_name_is_immune_to_backup_pruning`.

### 4.2 Known gap — search is built but unreachable

`search_articles()` is now FTS5-backed and correct, but **nothing calls it**:
there is no `/api/*` search route, and the TopBar search box
(`src/components/layout/TopBar.tsx`) submits `GET /?search=term` to a param no
page reads. Verified in the browser: with `?search=…` set, the app still
requests `/api/articles?limit=30&offset=0`. Wiring this up is its own task —
add the route, then point the existing box at it.

Note the FTS5 path matches whole tokens, where the old LIKE path matched
substrings. If partial-word matching matters, append `*` to the final token
for a prefix query — `_sanitize_fts5_query` currently quotes every token,
which deliberately disables all operators including `*`.

---

## 5. Wave 2

### 5.1 B-ui — Console restore UI (`src/pages/ConsolePage.tsx` only)

Depends on B-backend's endpoints; read the actual route signatures before coding.

- Add a section listing backups (name, size, date, auto/manual), a restore button
  per row, and a file picker to upload a `.db`.
- **Use a two-step inline confirm**, modelled on the existing prune flow in the
  same file — *not* `alert()`/`confirm()`, which is what every other action there
  currently uses. Restoring a database deserves better than a native dialog.
- Upload the file as a raw body (`fetch(..., { method: 'POST', body: file })`),
  matching the backend's `application/octet-stream` contract. There is no
  multipart support and `python-multipart` is not installed.
- After a successful restore the response says "staged": show a clear message
  that the user must **quit and reopen the app** to apply it. Do not imply it
  already happened.
- Read errors from `data.error` (existing convention in this file).

### 5.2 C-backend — weather API + history

Owns: new `routers/weather.py`, new `lib/scheduler/weather.py`, `main.py`
registration, `scheduler/service.py` job registration. Uses the models/repository
from wave 1 — read them first, don't re-create them.

- Proxy Open-Meteo behind `/api/weather/*`. Provider details are in
  `src/lib/weather/api.ts`: forecast `api.open-meteo.com/v1/forecast`, geocoding
  `geocoding-api.open-meteo.com/v1/search`, keyless.
- Cache with a TTL following `routers/finance.py` (constants at the top of the
  module, cache-aside read/refresh flow).
- **Open-Meteo returns `daily` as columnar parallel arrays** (`time[]`,
  `temperature_2m_max[]`, …) indexed by position. Pivot to one row per
  (location, date) on write.
- **Backfill history from the archive API** (`archive-api.open-meteo.com/v1/archive`,
  free, decades of data) so timelines are useful immediately rather than after
  weeks of accumulation.
- Hourly snapshot job for saved locations, registered per §3.4.
- Retention: prune old observations, following `delete_old_heatmap_snapshots`.

---

## 6. Wave 3

### 6.1 C-frontend — repoint + timeline

Owns `src/lib/weather/*`, `src/components/weather/*`, weather CSS in
`globals.css`.

- Repoint `api.ts` from Open-Meteo to `/api/weather/*` (fixes §3.3).
- Cities become server-persisted; user-added cities must survive a reload, which
  they currently do not.
- Add a temperature timeline, high/low records, and city comparison. Chart it by
  hand with SVG or CSS — **do not add a charting library** (§0.6). `wind_speed_10m_max`
  is already fetched but never displayed.

### 6.2 E-backend — daily briefing

Owns new `routers/briefing.py`, briefing model + repository, scheduler job.

- Table keyed by unique date (same shape as `MarketHeatmapSnapshot`), storing
  content + model + created_at, so repeat views are free.
- Generate from the day's top-ranked articles, reusing the ranking scorer and
  `lib/integrations/ollama.py` / `lib/services/summarization.py`.
- **Exclude Manual Links**, matching `lib/scheduler/summarizer.py`.
- Daily cron plus an on-demand regenerate endpoint.
- Ollama may be offline — `/api/health` reports `ollama:false` and the app must
  stay usable. Fail soft.

---

## 7. Wave 4

### 7.1 E-frontend — briefing page

New page + route in `src/main.tsx` + a sidebar link in
`src/components/layout/Sidebar.tsx` (put it in the LIBRARY group next to
Podcasts). Handle three states explicitly: no briefing yet, generating, and
Ollama offline.

---

## 8. Definition of done

For every task:

1. `.venv/bin/python -m pytest backend/tests -q` — all pass.
2. `npm run lint` — no new warnings beyond the known `ThemeProvider` one.
3. `npm run build` — succeeds (if you touched the frontend).
4. **New tests for new behaviour**, including at least one that would have caught
   the specific bug class your change risks. Security-relevant code gets negative
   tests (hostile input rejected), not just happy-path ones.
5. Verified **end to end**, not just unit-tested — start the stack and exercise
   the real route/page. Report the actual observed values.
6. A report stating: what changed, what you verified and how, and explicitly what
   you could *not* verify.
