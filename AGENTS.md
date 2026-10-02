# AGENTS.md — working rules for this repo

Newsixity is a local-first news/RSS/podcast reader: a React 19 + Vite frontend
(`src/`), a Python FastAPI backend (`backend/app/`), and a Tauri 2 shell
(`src-tauri/`) that spawns the backend as a sidecar and points the webview at
it. There are **no Tauri IPC commands** — the frontend talks to the backend
with plain `fetch()` against a `127.0.0.1` port chosen at startup.

## Never delete data without asking

This app's databases are the user's reading history, subscriptions, and saved
articles. They are not reproducible from the repo. Treat them as precious.

**Never, without explicit permission in the current conversation:**

- Delete, truncate, drop, or move a `.db` / `.sqlite` / `.sqlite3` file
- Run `DELETE FROM`, `DROP TABLE`, `TRUNCATE`, or `db.drop_all()`
- `rm` anything under `data/`, or a `newsixity.db` in Application Support
- Recreate a database to work around a schema or migration problem
- Reset, reseed, or wipe state to get a clean run

Two separate databases exist, and confusing them is a common way to "fix" a bug
by destroying data:

| Context | Path |
|---|---|
| Dev (`NEWSIXITY_DB_PATH` unset) | `data/newsixity.db` |
| Packaged macOS app | `~/Library/Application Support/Newsixity/newsixity.db` |

`backend/app/config.py` picks between them. If a query "fails because the
table/column doesn't exist", that is a **migration bug to fix**, not grounds
for touching the file. There is no migration framework; post-hoc columns are
backfilled idempotently at startup by helpers like
`_add_column_if_missing` in `backend/app/db/init_db.py`. Extend that pattern —
never recreate the table.

**Point disposable runs at a temp database instead.** `tests/conftest.py` sets
`NEWSIXITY_DB_PATH` before importing `app.db.session` because the engine is a
module-level singleton; do the same in any scratch script:

```sh
NEWSIXITY_DB_PATH=/path/to/scratch.db backend/.venv/bin/python -m pytest
```

If you believe a destructive change is genuinely required, stop and ask. Say
what you'd delete, why, what breaks without it, and what the recovery path is.
"Even if you're sure" applies — including when a fix looks obviously correct.
A backup is not consent; ask first.

## Prove a fix before calling it done

No bug fix ships on inspection alone. For every fix:

1. **Reproduce the failure first.** Get a red test that fails for the stated
   reason, with the error message confirming your diagnosis. A test that fails
   for the wrong reason proves nothing.
2. **Make it pass.**
3. **Show the full suite still green** — not just your new test:
   ```sh
   cd backend && .venv/bin/python -m pytest -q     # backend
   npx tsc --noEmit && npx eslint src && npm run build   # frontend
   ```
4. If step 1 wasn't possible (no test harness for that layer, e.g. most of the
   frontend), say so explicitly and name what you verified instead. Don't let
   "it typechecks" stand in for "it works".

**When adding tests, pin the bug, not the code.** Assert the specific
behaviour that was broken so it cannot silently regress — not a snapshot of
whatever the current implementation happens to return.

## Silent failure is the recurring defect class

This codebase fails *quietly* far more often than it fails loudly. Most shipped
bugs here are a swallowed error that renders an empty box:

- `src/lib/utils/apiError.ts` only reads `detail`. Bodies using `error`, and
  non-JSON 5xx, silently collapse to a generic fallback string.
- Frontend `fetch` wrappers check `if (res.ok)` and then throw away the body.
- `if (feed_data.bozo)` rejects feeds on any parse *warning*, not just failure.

When a view renders empty, ask what error was discarded. If a response handler
ignores a non-OK status, that's the bug — surface it. Don't widen a `catch`
or add a fallback to hide it.

## Conventions

- **All CSS lives in `src/app/globals.css`.** No Tailwind, no CSS modules, no
  new `.css` files. Plain class names, BEM-ish, grouped under `── section ──`
  comment banners.
- The app shell owns the viewport: `.layout` is `100dvh` with `overflow:
  hidden`, `html/body/#root` are `height: 100%`, and `.main` is the single
  content scroll container. Don't reintroduce `min-height: 100vh` or
  document-level scrolling — that's what makes long pages slide out from under
  the sidebar.
- Backend: `routers/` for HTTP, `lib/` for logic, `db/repository/` for queries.
  Routes map domain exceptions to status codes; they don't catch bare
  `Exception` and discard the cause.
- Validation and SSRF gating live in `lib/integrations/` (`parse_http_url`,
  `resolves_to_blocked_ip`, redirect-hop re-checking, byte caps). New
  user-supplied fetch paths must go through the same gate.
- Python tests under `backend/tests/{basic,integration,security,database}`.
  There are no frontend tests yet — if you add one, note it.
- Keep changes scoped. Don't reformat untouched code.

## Before finishing

- TypeScript clean (`npx tsc --noEmit`), eslint clean, `npm run build` succeeds
- Backend suite fully green
- Tell the user what was wrong, what you changed, and what you ran to verify
- Call out anything you deliberately left undone, and any unrelated problem you
  noticed but didn't touch