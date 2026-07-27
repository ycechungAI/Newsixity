# Newsixity v0.4 — notes

Captured while finishing v0.3. Read `spec-v0.3.md` first for the invariants
(route ordering, SSRF gate, no-Alembic migrations, WAL, frontend constraints)
— they all still apply.

---

## 1. User-managed feeds

Today feeds are seeded into the database and there is no way to add one from
the UI. `POST /api/feeds` does not exist; Settings can only reweight the feeds
that are already there.

**Wanted:** add, edit, disable, and remove RSS/Atom feeds from Settings.

Notes for whoever builds it:

- The repository layer already has most of what's needed (`get_all_feeds`,
  `update_feed_source_weight`); the gap is create/delete plus a router.
- **Validate the URL through the SSRF gate before fetching it.** A
  user-supplied feed URL is the one place in this app where an arbitrary
  outbound address reaches the server. Reuse `parse_http_url()` +
  `resolves_to_blocked_ip()`, exactly as `fetch_podcast_feed()` does — do not
  hand-roll a check.
- Verify the URL actually parses as a feed *before* saving it, and surface
  the failure. A feed row that silently never fetches is the same failure
  class as the bugs listed in §6.
- Deleting a feed must not orphan its articles — decide explicitly between
  cascade-delete and reassign, and cover it in `test_data_integrity.py`.
- New categories may be needed if users add feeds outside the existing set;
  `CAPPED_CATEGORIES` and the sports keyword filter both assume the current
  fixed slugs.

## 2. Broader search — user-defined search links

Search currently covers only what is already in the local database (FTS5 over
title, content, summary). That is a floor, not a ceiling.

**Wanted:** let the user add their own search targets so a query can reach
beyond stored articles.

Two distinct pieces, worth keeping separate:

- **Search-link templates.** User-defined URLs with a placeholder, e.g.
  `https://news.ycombinator.com/from?site={q}`. The results page renders them
  as one-click outbound links. Cheap, no scraping, no ToS questions — this
  alone covers a lot of "search breadth".
- **Federated results.** Actually fetching and merging remote results into
  the results list. Much more involved: every source needs its own parser,
  must go through the SSRF gate and a timeout budget, and must degrade to
  local-only results when a source fails. `SearchResults.tsx` already contains
  an abandoned attempt at scraping search-engine HTML — read it before
  starting, and note why it was left unfinished.

Related smaller wins while in here:

- Search filters: by category, by date range, saved-only.
- Highlight matched terms in results — FTS5 has `snippet()` and `highlight()`
  built in, so this is nearly free.
- Search within a single feed or category from that category's page.

## 3. Daily AI briefing

Planned for v0.3 and never built — moved here as a first-class v0.4 feature
rather than a leftover.

A once-a-day summary of what actually mattered, generated locally from the
articles already in the database. Nothing leaves the machine: it runs through
the same Ollama instance the summarizer uses.

Shape:

- **Table** `daily_briefing` — unique `date`, `content`, `model`,
  `created_at`. Same shape as `MarketHeatmapSnapshot` (`db/models.py`); a
  unique date is what makes "generate once, serve many times" safe.
  `create_all()` picks up the new table; a new index on an *existing* table
  would need a line in `init_db.py`.
- **Generation** — take the day's top-ranked articles using the existing
  scorer, then `lib/integrations/ollama.py` /
  `lib/services/summarization.py`. **Exclude the Manual Links feed**, exactly
  as `lib/scheduler/summarizer.py` does — a briefing about the user's own
  saved links is noise.
- **Schedule** — a cron job in `lib/scheduler/service.py`, following the
  `BACKUP_HOUR` block already there (`max_instances=1`, `coalesce=True`).
  Plus an on-demand regenerate, because a briefing generated before the
  morning's articles arrived is worth redoing.
- **Serving** — cache by date. Ollama generation is slow and the answer for a
  past date never changes, so re-reading a briefing must never re-generate.
- **Frontend** — a `/briefing` page and a sidebar link next to Podcasts.

Watch for:

- **Ollama may be down or the model missing.** The briefing must degrade to a
  clear "not generated yet" state, never a spinner that hangs. There is now a
  `GET /api/ollama/health` (200 up / 503 down) to check cheaply.
- **Generation is slow** — do it in the background job, not in the request.
  Blocking I/O never goes in an `async def` (see spec-v0.3 §3.1).
- Register the route in `main.py` and **verify it end to end in the browser**;
  `test_api_contract.py` will catch a missing route, but only for endpoints
  the frontend actually calls.

## 4. Carry-overs from v0.3

- **Hourly weather scheduler** — observations are currently recorded when a
  forecast is viewed, which covers normal use but not a machine left idle.
- **Rebuild the desktop app** after any backend change:
  `./build-desktop-mac.sh`. The frozen sidecar does not pick up source edits.

## 5. Build, size, and environment — measured, don't re-derive

### Where the app's size actually is

Measured on the v0.3 macOS build (143 MB total):

| Part | Size |
|---|---|
| Python sidecar (`_internal`) | 119 MB |
| — babel locale-data | 31 MB → **trimmed to ~1 MB** |
| — pandas (via yfinance) | 17 MB |
| — cryptography | 11 MB |
| — lxml (via trafilatura) | 8.6 MB |
| — numpy (via yfinance) | 6.6 MB |
| Tauri binary | 3.9 MB |
| **Frontend `dist/`** | **372 KB** |

**`node_modules` (131 MB) ships nothing.** It is a build-time cost only; the
packaged app contains `dist/` plus the frozen Python. Trimming npm packages
does not shrink the app — don't spend effort there for size reasons. The
frontend is already 0.3% of the bundle.

The heavy Python packages are transitive, not chosen:
`yfinance → pandas, numpy, curl_cffi` and
`trafilatura → lxml, courlan → babel`. Removing them means dropping the
finance or content-extraction features, so weigh it as a feature decision.

**babel is already trimmed** in `newsixity-backend.spec`
(`_trim_babel_locales`): courlan imports `Locale` only to score language
codes in URL segments, which requires a `target_language` we never pass, and
it already catches `UnknownLocaleError`. Keep `root/en/en_US/en_GB`. Revisit
if language-aware extraction is enabled.

### Build script behaviour

- `./build-desktop-mac.sh` (or `npm run build:mac`) is the only entry point.
- Tauri rebuilds `Newsixity.app` **in place**, so an un-installed build is
  silently replaced by the next one. The script now keeps a timestamped copy
  in `install_file/` (last 3 retained, gitignored).
- It **verifies** the bundle after building — binary present, Python resource
  present — rather than trusting the build's own success summary, which
  prints a DMG path even when only a scratch image was produced.
- The DMG step can leave `bundle/macos/rw.*.dmg` scratch images (~180 MB
  each) that nothing cleans up; the script removes them before and after.
  If `dmg/` has no final `.dmg`, the `.app` is still complete and installable.

### The venv trap

`start.sh` used to delete and rebuild `.venv` on **every** run: the staleness
check parsed the recorded path with `cut -d'"' -f2`, but `python3 -m venv`
writes `VIRTUAL_ENV=/path` unquoted, and `cut` on a line with no quote
returns the whole line. Fixed — but note the knock-on: a `.venv` rebuild
drops **pyinstaller** unless the `desktop` extra is installed, and then
`build-desktop-mac.sh` fails with "pyinstaller not found in .venv".
`start.sh` now installs `.[dev,integrations,desktop]`. If a desktop build
ever fails that way again, this is why:

```bash
.venv/bin/pip install -e "backend/.[dev,integrations,desktop]"
```

### Dead weight removed in v0.3

- Root `tests/` — the old Next.js TypeScript suite. Unrunnable (no test
  runner configured, imported three deleted modules and `better-sqlite3`,
  which was never a dependency) and fully superseded by `backend/tests/`.
  Verified 1:1 before deleting; `test_schema.py` covers everything
  `crud.test.ts` did. Removing it took `tsc` from 20 errors to 3.
- `tsc` is now at **0 errors** — keep it there, it was hiding a real one
  (`below_threshold` missing from `PrunePreview`, a field the API does
  return).

## 6. The bug class to keep testing for

Five bugs in v0.3 were all the same shape: **a feature wired on one side and
silently doing nothing on the other.** None of them threw an error, and every
unit test passed.

- Playlists fetched youtube.com from the browser — no CORS header, so every
  request was blocked and the `catch` returned an empty list.
- The top-bar search box submitted `?search=` to a parameter no page read.
- `search_articles()` was FTS5-correct but had no HTTP route at all.
- `GET /api/feeds/weights` did not exist (only PUT), so Feed Rankings got
  `index.html` at status 200 and rendered empty.
- `GET /api/ollama/health` did not exist either.

The reason these hid: a missing API route returned 200 with the SPA's HTML
via the static catch-all, so `res.ok` was true and only the JSON parse failed
— usually inside a `catch` that swallowed it.

**This is now fixed at the root.** `SPAStaticFiles.get_response` in
`app/main.py` returns a JSON 404 for unmatched `/api/*` instead of falling
through to `index.html`. Client-side routes (`/finance`, `/article/123`, …)
still get the SPA. Pinned by `TestUnknownApiPathsFailLoudly` in
`tests/integration/test_static_routes.py` — **do not "restore" the fallback
for /api paths**, it is the single change that makes this whole class fail
loudly.

`backend/tests/integration/test_api_contract.py` now scans the frontend for
`fetch("/api/…")` calls and asserts each one exists with the right method. It
caught the Ollama one immediately. **Keep it passing, and prefer extending it
over adding narrow one-off tests** — it is the cheapest guard against this
whole class.

When adding a feature, verify the round trip end to end in the browser, not
just the unit. The user found four of these five by clicking; the tests should
be catching them first.
