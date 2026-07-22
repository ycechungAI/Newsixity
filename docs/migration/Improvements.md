# Improvements & Slimming Backlog

> Status: **Open** · Last updated: 2026-07-22 (Sonnet 5 storage-trim pass)
> Related: [spec.md](spec.md) · [todo.md](todo.md)
> Each task tagged `[PRIORITY · Model]` — **Haiku 4.5** (mechanical/shell) · **Sonnet 5** (code changes needing judgment) · **Opus 4.8** (architecture/security).

Measured after the 2026-07-22 trim (working tree **~1.1 GB**, down from 1.9 GB):

| Item | Size | Tracked? | Action |
|---|---|---|---|
| `node_modules` | 441 M | no | fixed cost of Next.js + its per-platform SWC binary; nothing safely prunable |
| `.venv` | 223 M | no | ~68 M is pandas/numpy/curl_cffi (yfinance's bot-detection bypass) — **kept intentionally**, see below |
| `data/` (DB 117M + WAL 3M + backups) | varies | no (gitignored) | backups now capped at 2+2, was 3+10 |
| `.next` | cleared (was 240 M) | no | build cache — regenerates on next `dev`/`build` |
| ~~`data_backup_20260212_021418/`~~ | deleted (was 5.9 M) | was tracked, already git-rm'd in `e614e10` | **done** — on-disk leftover removed 2026-07-22 |
| ~~`graphify-out/`~~ | deleted (was 1.3 M) | already gitignored | **done** — on-disk leftover removed 2026-07-22 |
| ~~`database.sqlite`, `.newsixity.db`~~ | deleted (0 B) | `.newsixity.db` was still tracked | **done** — git-rm'd + deleted 2026-07-22 |
| `backend/.venv` | deleted (was 196 M) | no | **done** — unused duplicate of root `.venv`, nothing referenced it |
| `package-lock.json` | 232 K | yes | pnpm already removed (`45abe48`), single lockfile |

## A. Size-reduction levers (for the migration end-state)

- [x] **[Haiku 4.5]** Drop Playwright → `httpx` + `trafilatura` (HTTP-only). Done in Stage 4; `playwright-core` removed from `package.json` in `e5cbc8a`.
- [ ] ~~Multi-stage Docker~~ — N/A, no Docker deployment planned (see [todo.md](todo.md) Stage 10).
- [ ] **[LOW]** Precompress static export assets (`.br`/`.gz`) if serving over a slow link — not done, low priority for a single-user local app.
- [x] **[Sonnet 5]** yfinance (→ pandas/numpy/curl_cffi, ~68 MB) evaluated for replacement 2026-07-22 — **kept deliberately**. curl_cffi exists specifically to mimic browser TLS fingerprints past Yahoo's bot detection; a plain-httpx rewrite would drop that protection and risk more 403s than yfinance already gets. Revisit only if Yahoo's blocking becomes a bigger problem than the disk cost.

## B. Git hygiene (do independently of migration)

- [x] **[Haiku 4.5]** `git rm --cached` graphify-out/data_backup/database.sqlite/.newsixity.db + gitignore — done in `e614e10`.
- [x] **[Sonnet 5]** Delete the actual on-disk leftovers the git-untrack didn't remove (`data_backup_20260212_021418/`, `graphify-out/`, `database.sqlite`, `.newsixity.db`, plus `git rm` the still-tracked empty `.newsixity.db`) — done 2026-07-22.
- [x] **[Haiku 4.5]** Pick one package manager; pnpm removed (`45abe48`).
- [ ] **[LOW · Haiku 4.5]** Consolidate root-level doc sprawl (`BACKUP_SYSTEM.md`, `BEHAVIOR_SUMMARY.md`, `FINAL_BEHAVIOR.md`, `IMPLEMENTATION_SUMMARY.md`, `PLAN.md`, `DEEP-RESEARCH-*.md`, `To DO.md`, …) into `docs/`.

## C. Data compaction (safe, non-destructive first)

- [x] **[Haiku 4.5]** `PRAGMA wal_checkpoint(TRUNCATE)` + `VACUUM` on `data/newsixity.db` — done in Phase 4 (108.62 → 100.87 MB).
- [x] **[Sonnet 5]** Lower backup cap — fixed 2026-07-22. Found this was two *separate* `MAX_BACKUPS` constants that had drifted apart: `app/routers/console.py` (manual backups, already lowered 10→3 in Phase 4) and `app/lib/scheduler/backup.py` (**automatic** daily/startup backups — still `10`, untouched by the earlier fix, capable of silently growing to ~1 GB). Both now set to `2` per user decision.
- [x] **[Sonnet 5]** Backups already use `VACUUM INTO` in both `console.py::create_backup` and `scheduler/backup.py::_create_daily_backup_sync` — snapshots are already compacted on creation, nothing further to do here.

## D. Performance TODOs to carry into the FastAPI port

These are open items from the legacy `To DO.md` (#19–24). Re-implement the fixes in
the Python version rather than reproducing the N+1 patterns.

- [ ] **[MED/HIGH · Sonnet 5]** N+1 in `getArticleGroupsByCategory` (`src/lib/db/queries.ts:216-234`) — up to ~90 queries per category page. Port as a single JOIN/`IN`.
- [ ] **[MEDIUM · Sonnet 5]** `ArticleCard.tsx:44-70` fires one `PATCH /api/articles/{id}` per card on scroll — batch into one "mark read" call.
- [ ] **[MEDIUM · Sonnet 5]** `rss/scheduler.ts:53-56` calls `getArticleById` per new article per refresh — batch with `WHERE id IN (...)`.
- [ ] **[LOW/MED · Haiku 4.5]** `getCachedQuotes` (`queries.ts:~1241`) loops per symbol — one `IN (...)` query.
- [ ] **[LOW/MED · Haiku 4.5]** Add compound index `(is_read, published_at)` — hit on nearly every page load; only `is_saved` is indexed today (`schema.ts:132`).
- [ ] **[LOW · Haiku 4.5]** `api/console/backup/route.ts:15-70` uses sync `readdirSync`/`statSync` in a handler — use async I/O in the FastAPI port.
