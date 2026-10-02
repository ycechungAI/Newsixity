# Copilot instructions for Newsixity

Project rules live in **AGENTS.md** at the repo root — read it and follow it.
See below for the two that matter most.

## Never delete data without asking

Never delete, truncate, drop, move, reset, reseed, or recreate a database.
`data/newsixity.db` (dev) and `~/Library/Application Support/Newsixity/newsixity.db`
(packaged macOS app) hold real reading history and cannot be regenerated.

A "table or column doesn't exist" error is a migration bug to fix (see
`_add_column_if_missing` in `backend/app/db/init_db.py`), not a reason to touch
the database file. For disposable runs, set `NEWSIXITY_DB_PATH` to a temp file.

## Prove fixes

Reproduce the bug with a failing test first, then fix it, then show the full
suite green: `cd backend && .venv/bin/python -m pytest -q` and
`npx tsc --noEmit && npx eslint src && npm run build`.

## Architecture notes

- No Tauri IPC commands. The React frontend calls the FastAPI sidecar with
  plain `fetch()` on a loopback port. Handlers live in `backend/app/routers/`.
- All CSS is in `src/app/globals.css` — no Tailwind, no CSS modules.
- Silent failure is the recurring defect class: most shipped bugs are swallowed
  errors rendering empty UI.
