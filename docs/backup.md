# Database Backup

## Where backups live

- Dev mode: `data/backups/`
- Packaged app: `<app-data>/backups/` next to the real database — e.g.
  `~/Library/Application Support/Newsixity/backups/` on macOS
  (`settings.resolve_db_path().parent / "backups"`).

## Automatic daily backups

`backend/app/lib/scheduler/backup.py` creates a `newsixity-auto-<timestamp>.db`
snapshot immediately on app startup and again at 3 AM local time every day
(scheduled via APScheduler in `main.py`'s lifespan). The blocking `VACUUM
INTO` runs in a worker thread so it never stalls the event loop.

**Retention: the 2 most recent automatic backups are kept** — older ones are
deleted automatically after each run (`MAX_BACKUPS = 2`).

## Manual backup

Click **BACKUP** in the Console page (`/console`) →
`POST /api/console/backup` (`backend/app/routers/console.py`), rate-limited
to 3/hour. Creates `newsixity-<timestamp>.db`.

**Retention: the 2 most recent manual backups are kept**, tracked
separately from automatic backups (same `MAX_BACKUPS = 2` cleanup, distinct
filename prefix).

## Backup method

`VACUUM INTO` via a raw `sqlite3` connection (not the ORM session — `VACUUM
INTO` cannot run inside a transaction) produces a clean, compact, single-file
snapshot. It captures the entire database: articles, saved articles, manual
links, article groups, feed configs, user preferences, settings, research
cache, stock watchlist.

## Restore from backup

```bash
# Stop the app first.
ls -lh data/backups/                     # list available backups (dev mode)

cp data/newsixity.db data/newsixity.db.old   # keep current state, just in case
cp data/backups/<backup-file>.db data/newsixity.db

# Restart the app.
```

For a packaged app, substitute the app-data path (e.g.
`~/Library/Application Support/Newsixity/`) for `data/`.

## Verify a backup

```bash
sqlite3 data/backups/<backup-file>.db "PRAGMA integrity_check;"
# Should output: ok
```
