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
- [x] **[Sonnet 5]** Consolidate root-level doc sprawl — done 2026-07-26 (v0.2 D.4). `BACKUP_SYSTEM.md`, `FINAL_BEHAVIOR.md`, `DEEP-RESEARCH-SETUP.md` folded into `docs/{backup,ranking,deep-research}.md` with corrected paths and behavior (retention is actually 2 backups not "forever"; ranking never deletes articles, only badges them — confirmed against `promoter.py`'s "DELETION IS DISABLED" comment). `PLAN.md`, `BUGS.md`, `IMPLEMENTATION_SUMMARY.md`, `DEEP-RESEARCH-TODO.md`, `BEHAVIOR_SUMMARY.md` (contradicted `FINAL_BEHAVIOR.md` — described a deletion-based design that was never shipped), `STARTUP.md` (wrong port/browser, non-reproducible LaunchAgent), `To DO.md` deleted as fully superseded/obsolete. `README.md` and `docs/DEVELOPER_GUIDE.md` rewritten — both were still describing the pre-migration Next.js stack.

## C. Data compaction (safe, non-destructive first)

- [x] **[Haiku 4.5]** `PRAGMA wal_checkpoint(TRUNCATE)` + `VACUUM` on `data/newsixity.db` — done in Phase 4 (108.62 → 100.87 MB).
- [x] **[Sonnet 5]** Lower backup cap — fixed 2026-07-22. Found this was two *separate* `MAX_BACKUPS` constants that had drifted apart: `app/routers/console.py` (manual backups, already lowered 10→3 in Phase 4) and `app/lib/scheduler/backup.py` (**automatic** daily/startup backups — still `10`, untouched by the earlier fix, capable of silently growing to ~1 GB). Both now set to `2` per user decision.
- [x] **[Sonnet 5]** Backups already use `VACUUM INTO` in both `console.py::create_backup` and `scheduler/backup.py::_create_daily_backup_sync` — snapshots are already compacted on creation, nothing further to do here.

## D. Performance TODOs to carry into the FastAPI port

These are open items from the legacy `To DO.md` (#19–24). Re-implement the fixes in
the Python version rather than reproducing the N+1 patterns.

- [x] Fixed during the Stage 1b port — `article_groups.py`'s N+1 eliminated (1+2N queries → 3); see `backend/STAGE_1B_HANDOFF.md`.
- [x] **[Sonnet 5]** Done 2026-07-26 (v0.2 D.1) — new `PATCH /api/articles` bulk endpoint + a module-level queue (`src/lib/articles/markReadQueue.ts`) shared across every `ArticleCard`, flushing one batched request instead of one PATCH per card. Verified: a 30-card page produces exactly one `PATCH /api/articles` call.
- [x] Fixed earlier in the v0.2 pass (D.2) — `refresh.py` now uses `get_articles_by_ids()` (single `WHERE id IN (...)` query) instead of one `get_article_by_id()` call per inserted article.
- [x] Already fixed in the port — `get_cached_quotes()` in `backend/app/db/repository/finance.py` is a single `IN (...)` query, used by the finance router.
- [x] Fixed earlier in the v0.2 pass (D.3) — `idx_articles_is_read_published` compound index added to `models.py` + an explicit `CREATE INDEX IF NOT EXISTS` in `init_db.py` (required since `create_all()` doesn't alter existing tables).
- [ ] **[LOW]** Still open: `backend/app/routers/console.py::create_backup` (the manual-backup endpoint) does synchronous `VACUUM INTO`/`iterdir`/`unlink` directly in an `async def` handler, blocking the event loop for its duration — unlike the scheduled daily backup (`lib/scheduler/backup.py`), which correctly wraps the same work in `asyncio.to_thread`. Low impact (rate-limited to 3/hour, DB is small), but worth the same fix for consistency.

## E. Desktop build workflow (macOS)

- [x] **[Sonnet 5]** Done 2026-07-26 — single command-line entry point for
      rebuilding the macOS app after **any** code change, from any tool/model,
      without needing an agent session to drive it: `./build-desktop-mac.sh`
      (or `npm run build:mac`) chains frontend build → PyInstaller freeze →
      resource install → `tauri build` into one call. Fixed a real bug found
      along the way: `backend/build_sidecar.sh` called `pyinstaller` without
      `--noconfirm`, so every rebuild after the first failed with "output
      directory is not empty" (PyInstaller's `COLLECT` step refuses to write
      into leftover `backend/dist/newsixity-backend/` from the prior build) —
      previously required manually `rm -rf backend/build backend/dist` before
      each rebuild, now handled automatically. `docs/desktop.md` updated to
      lead with the one-command flow (troubleshooting entry for the old error
      removed, since the root cause is fixed rather than worked around).
      Rebuilding never touches `~/Library/Application Support/Newsixity/` —
      user data lives outside the build output, and the packaged app only
      seeds that DB on first launch when it doesn't already exist (see
      `backend/app/db/init_db.py::_copy_seed_db_if_first_run`).
