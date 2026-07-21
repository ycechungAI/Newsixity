# Improvements & Slimming Backlog

> Status: **Open** · Last updated: 2026-07-21
> Related: [spec.md](spec.md) · [todo.md](todo.md)
> Each task tagged `[PRIORITY · Model]` — **Haiku 4.5** (mechanical/shell) · **Sonnet 5** (code changes needing judgment) · **Opus 4.8** (architecture/security).

Measured baseline (working tree **1.9 GB**, git-tracked `.git` only **4.8 MB**):

| Item | Size | Tracked? | Action |
|---|---|---|---|
| `node_modules` | 1.3 G | no | regenerable — delete/reinstall freely |
| `data/` (DB 109M + WAL 15M + backups 201M) | 325 M | no (gitignored) | prune + compact |
| `.next` | 268 M | no | build cache — delete freely |
| `data_backup_20260212_021418/` | 5.9 M | **yes (3 files)** | untrack |
| `graphify-out/` | 1.3 M | **yes (24 files)** | untrack (churns every session) |
| `database.sqlite`, `.newsixity.db` | 0 B | **yes** | untrack (empty placeholders) |
| `package-lock.json` + `pnpm-lock.yaml` | 468 K | yes | keep one package manager |

## A. Size-reduction levers (for the migration end-state)

- [ ] **[HIGH · Haiku 4.5]** Drop Playwright → `httpx` + `trafilatura` (HTTP-only). Saves ~300 MB. *(locked — see spec §2)*
- [ ] **[HIGH · Sonnet 5]** Multi-stage Docker: `node` build stage emits `dist/`; final `python:3.12-slim` copies only `dist/` + venv. Node never ships.
- [ ] **[MEDIUM · Sonnet 5]** Vite production build: minify, tree-shake, code-split, precompress `.br`/`.gz`; FastAPI serves compressed assets.
- [ ] **[MEDIUM · Haiku 4.5]** Python hygiene: slim base, `--no-cache-dir`, no dev deps in runtime layer, wheels only.
- [ ] **[LOW · Sonnet 5]** Evaluate whether `yfinance` (→ pandas/numpy, ~70 MB) can be replaced with a lighter HTTP client for the quotes actually used.

## B. Git hygiene (do independently of migration)

- [ ] **[HIGH · Haiku 4.5]** `git rm -r --cached graphify-out data_backup_20260212_021418 database.sqlite .newsixity.db`
- [ ] **[HIGH · Haiku 4.5]** Add to `.gitignore`: `graphify-out/`, `data_backup_*/`, `*.sqlite`, `.newsixity.db`
- [ ] **[MEDIUM · Haiku 4.5]** Pick one package manager; delete the other lockfile. Remove `pnpm` from `package.json` deps (it's a tool, not a dependency).
- [ ] **[LOW · Haiku 4.5]** Consolidate root-level doc sprawl (`BACKUP_SYSTEM.md`, `BEHAVIOR_SUMMARY.md`, `FINAL_BEHAVIOR.md`, `IMPLEMENTATION_SUMMARY.md`, `PLAN.md`, `DEEP-RESEARCH-*.md`, `To DO.md`, …) into `docs/`.

## C. Data compaction (safe, non-destructive first)

- [ ] **[HIGH · Haiku 4.5]** `PRAGMA wal_checkpoint(TRUNCATE)` + `VACUUM` on `data/newsixity.db` (15 MB WAL, 109 MB main).
- [ ] **[HIGH · Haiku 4.5]** Lower backup cap (`MAX_BACKUPS = 10` currently → ~1 GB projected at ~100 MB/snapshot) and/or gzip snapshots.
- [ ] **[MEDIUM · Sonnet 5]** Switch backups to `VACUUM INTO` so snapshots are already compacted.

## D. Performance TODOs to carry into the FastAPI port

These are open items from the legacy `To DO.md` (#19–24). Re-implement the fixes in
the Python version rather than reproducing the N+1 patterns.

- [ ] **[MED/HIGH · Sonnet 5]** N+1 in `getArticleGroupsByCategory` (`src/lib/db/queries.ts:216-234`) — up to ~90 queries per category page. Port as a single JOIN/`IN`.
- [ ] **[MEDIUM · Sonnet 5]** `ArticleCard.tsx:44-70` fires one `PATCH /api/articles/{id}` per card on scroll — batch into one "mark read" call.
- [ ] **[MEDIUM · Sonnet 5]** `rss/scheduler.ts:53-56` calls `getArticleById` per new article per refresh — batch with `WHERE id IN (...)`.
- [ ] **[LOW/MED · Haiku 4.5]** `getCachedQuotes` (`queries.ts:~1241`) loops per symbol — one `IN (...)` query.
- [ ] **[LOW/MED · Haiku 4.5]** Add compound index `(is_read, published_at)` — hit on nearly every page load; only `is_saved` is indexed today (`schema.ts:132`).
- [ ] **[LOW · Haiku 4.5]** `api/console/backup/route.ts:15-70` uses sync `readdirSync`/`statSync` in a handler — use async I/O in the FastAPI port.
