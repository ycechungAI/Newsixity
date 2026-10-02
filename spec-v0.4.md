# Newsixity v0.4 — spec

Captured while finishing v0.3, then updated 2026-10-02 against the working
tree before implementation started. Read `spec-v0.3.md` first for the
invariants (route ordering, SSRF gate, no-Alembic migrations, WAL, frontend
constraints) — they all still apply.

## Status / definition of done

v0.4 is done when every box below is ticked, `pytest backend/tests` is green,
`tsc --noEmit` is at 0 errors, `npm run lint` is clean for `src/`, and each
feature has been clicked through end to end in the browser.

- [x] §0 Ask Newsixity — finish and fix the in-progress implementation
- [x] §0.1 Ollama start prompt — backend half is missing
- [x] §1 User-managed feeds (add / edit / disable / delete)
- [x] §2a Search-link templates
- [x] §2b Federated results (one provider: Hacker News via Algolia API)
- [x] §2c Search filters (category, date range, saved-only) + FTS5 highlights
- [x] §3 Daily AI briefing
- [x] §4 Carry-overs: react-router 7, Topics controls, hourly weather job
- [x] Desktop build verified (`./build-desktop-mac.sh`) — 0.4.0 `.app`, 138 MB; frozen sidecar smoke-tested against every new endpoint

Baseline found on 2026-10-02 before any v0.4 work: 5 failing tests —
`test_ollama_optional.py` ran its subprocess from `backend/tests` instead of
`backend/` (fixed: `parents[2]`), and `test_api_contract.py` flagged
`POST /api/ollama/start` (see §0.1 — the contract test doing its job).

### Found and fixed during v0.4 (not in the original notes)

Every one of these is the §6 bug class — wired on one side, silently doing
nothing on the other — and each now has a regression test.

- **Feed refresh aborted on every run** on a fresh database.
  `seed_all_feeds()` runs on *every* refresh and `seed_feed()` treated a
  feed as existing only when category **and** name **and** URL matched.
  Hacker News is seeded by `init_db` under Security and by `DEFAULT_FEEDS`
  under Technology, so the insert hit the URL unique constraint and the
  whole refresh died — zero articles. It would also have fired for any
  default feed a user renamed or moved (§1). Now keyed on URL only, and it
  honours deleted-feed tombstones (`stats.py::seed_feed`).
- **Topic grouping never ran in the Python port.** `group_articles()` called
  the repository with a kwarg it doesn't take, read dicts as objects, and
  passed `create_group` arguments in the wrong order; the TypeError was
  swallowed into the refresh error list. No group was ever created.
- **The Topics view never grouped.** No page passed `groups` to
  `ArticleList`, so the default view was a flat list under another name.
  It now groups the fetched page by `groupId` client-side (§4).
- **Search results had no source, date, or saved state.**
  `/api/articles/search` returned snake_case dataclasses in a plain dict;
  `ArticleCard` reads camelCase. Now validated into the `Article` schema.
- **Ask could never find anything for a real question** — FTS ANDed every
  word, so "what happened with X?" required "what" and "happened". Ask now
  uses `match_any` (OR + question stopwords, bm25-ranked).
- **The scheduled RSS fetch had no SSRF gate**, and no fetch re-checked
  redirect hops. `rss.fetch_feed_bytes()` now gates every hop, caps size at
  10 MB, and is used by both refresh and the add-feed probe.
- The Manual Links feed (`internal://manual`) was "fetched" every refresh and
  recorded a bogus `last_error`; refresh now skips `internal://` feeds.
- Weather retention (`delete_old_weather_*`) was defined but never called;
  the hourly job now applies it.

---

## 0. Ask Newsixity (Perplexity-style Q&A)

Started 2026-10-01 outside this spec (tracked in `version_update_todo.md`),
uncommitted at the time of writing. A query box that returns a synthesized,
cited answer from the local article library instead of a result list.

What exists: `POST /api/ask` (`routers/ask.py`), `AskRequestBody` /
`AskHistoryTurn` in `schemas.py`, `answer_research_question(conversation=)`
in `lib/integrations/ollama.py`, `src/components/ask/AskPage.tsx`, an Ask
button in `TopBar`, the `/ask` route, `tests/integration/test_ask.py`.
Sessions are ephemeral — the frontend holds the thread and sends prior turns
back as `history`; no tables.

Must fix before it counts as done:

- **`AskPage.tsx` is styled with Tailwind classes.** There is no Tailwind in
  this app (spec-v0.3 §3.5), so the page renders unstyled. Restyle with
  plain classes in `globals.css` and the CSS custom properties. Move it to
  `src/pages/AskPage.tsx` with the other pages.
- **Model selection.** The router uses `get_setting("ollama_model") or
  "llama3.2"`; a model that isn't installed then fails with
  `OllamaModelNotFoundError`, which is not caught → 500. Use
  `get_default_model()` (installed-model aware) and treat model-not-found
  the same as Ollama offline (article fallback).
- **Error rendering.** `data.detail` from a 422 is an array — reuse the
  `apiErrorMessage()` helper (currently private to `PodcastsPage.tsx`; move
  it to `src/lib/utils/apiError.ts`).
- A sidebar link under Library, next to Podcasts.
- Extend `test_ask.py` with route-level tests (Ollama monkeypatched) for:
  no matches, Ollama offline → articles, success → cited sources.

## 0.1 Ollama start prompt

`src/components/OllamaStartPrompt.tsx` (mounted in `App.tsx`) asks to start
Ollama when the binary is installed but the server is down. The backend half
was never written: it reads `binaryInstalled` from `GET /api/ollama/models`
(field doesn't exist, so the prompt never opens) and calls
`POST /api/ollama/start` (route doesn't exist).

- `GET /api/ollama/models` gains `binaryInstalled: bool` —
  `shutil.which("ollama")` plus the standard install locations
  (`/usr/local/bin`, `/opt/homebrew/bin`, `/Applications/Ollama.app`,
  `%LOCALAPPDATA%\Programs\Ollama`), because the desktop app's sidecar does
  not inherit a login shell's `PATH`.
- `POST /api/ollama/start` — only when the configured host is local
  (`localhost`/`127.0.0.1`); spawns `ollama serve` detached (no shell, fixed
  argv), then polls `/api/tags` for up to ~10 s. Returns `{success, message}`;
  already running → success. Rate limited. Never takes a path or command
  from the request.
- Error text uses `var(--danger)`, not a hardcoded colour.

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

**Decisions (2026-10-02):**

- Endpoints: `POST /api/feeds` `{url, name?, categorySlug}`,
  `PATCH /api/feeds/{id}` `{name?, enabled?, categorySlug?}`,
  `DELETE /api/feeds/{id}`. Declare them **after** `/feeds/refresh` and
  `/feeds/weights` (route-ordering invariant).
- Create flow: `parse_http_url()` → `resolves_to_blocked_ip()` → fetch with
  the same timeout + size cap as the RSS refresh → `feedparser` must yield a
  feed title or at least one entry, otherwise 400 with the reason. Duplicate
  URL → 409. Name defaults to the feed's own title.
- Delete: **cascade unsaved articles, keep saved ones** by reassigning them to
  the Manual Links feed (`internal://manual`) — a user's saved articles must
  never vanish because a source was removed. `article_research` rows of
  deleted articles go with them. FTS5 stays in sync via the existing delete
  trigger. Empty `article_groups` are removed.
- The Manual Links feed cannot be edited or deleted (403).
- **Seed resurrection:** `init_db()` re-inserts the seeded security/sports
  feeds with `INSERT OR IGNORE` on every startup, so deleting one would bring
  it back on next launch. Deleting a feed records its URL in the
  `deleted_feed_urls` setting (JSON list) and seeding skips those URLs.
  Re-adding the URL by hand removes it from the list.
- Categories: the user picks an existing category. New categories are out of
  scope for v0.4 — uncapped categories already work (no daily cap applies),
  and the sports keyword filter only runs for the `sports` slug, so nothing
  breaks; adding category CRUD is a sidebar/ranking design question.
- Frontend: a "Feeds" section in Settings — add form (URL, optional name,
  category select), and per feed: enable toggle, rename, delete (confirm
  dialog), last error shown. Feed Rankings stays as is.

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

**Decisions (2026-10-02):**

- *Why the old attempt was abandoned:* `SearchResults.tsx` fetched
  search-engine HTML **from the browser** — blocked by CORS on every engine,
  and against their ToS anyway. It and `SearchResultsSummary.tsx` are imported
  by nothing; delete both (and `detectSearchEngine` if it becomes unused).
- **§2a templates:** stored as a JSON list in the `search_links` setting
  (`[{name, template}]`) — no table, the list is tiny and user-owned.
  `GET/PUT /api/search-links`. A template must be an http(s) URL containing
  `{q}` exactly once; the query is `encodeURIComponent`'d before
  substitution. Rendered as outbound chips on `/search`; managed in Settings.
  Seeded defaults when the setting is absent: Hacker News, Google News,
  DuckDuckGo, Wikipedia.
- **§2b federated:** one provider in v0.4 — Hacker News via the Algolia JSON
  API (`hn.algolia.com/api/v1/search`). A JSON API, not scraping, so no
  parser rot and no ToS problem. `GET /api/search/remote?q=` on the backend
  (never from the browser), through `parse_http_url()` +
  `resolves_to_blocked_ip()`, 5 s timeout; on any failure it returns
  `{results: [], error}` with status 200 and the page shows local results
  only. Rendered as a separate "From the web" block below local results —
  not merged into the local ranking, because bm25 scores and remote ranks are
  not comparable. More providers follow the same function shape.
- **§2c:** `GET /api/articles/search` gains `from`, `to` (ISO dates, on
  `published_at`) and `saved` filters; `category` already exists. Each hit
  gets `highlight` — FTS5 `snippet()` over the content column with `<mark>`
  markers. Snippets are HTML-escaped server-side before the markers are
  inserted (the content column is already HTML-stripped, but escape anyway),
  and the frontend renders only `<mark>` from it. Category pages get a
  "search this category" box that links to `/search?q=…&category=…`.

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

**Decisions (2026-10-02):**

- Endpoints: `GET /api/briefing?date=YYYY-MM-DD` (default today, local date)
  → `{date, content, model, createdAt, status}` where status is `ready` or
  `missing`; never 404, so the page can render "not generated yet" plainly.
  `POST /api/briefing/regenerate` → schedules generation as a background task
  and returns 202 `{status: "generating"}`; the page polls `GET`.
  `GET /api/briefing/dates` lists dates that have a briefing.
- Generation input: up to 20 articles published (or fetched) in the last 24 h,
  ordered by `relevance_score`, Manual Links excluded, each as title + summary
  (or first 400 chars of content). Prompt asks for 4–8 themed bullet points
  citing `[n]`; the stored `content` keeps the numbered source list
  (title + article id) so citations link back to `/article/{id}`.
- Concurrency: a module-level "generating" flag, like the summarizer's
  `_background_running`, so cron + button can't run two generations at once.
  Regenerate overwrites today's row (upsert on `date`); past dates are only
  regenerated if explicitly asked.
- Schedule: cron at `BRIEFING_HOUR = 7` local. Generation failure (Ollama
  down, no model, no articles) logs and stores nothing.

**As built:** citations live in a separate `sources` JSON column
(`[{n, articleId, title, feedName}]`) rather than inside `content`. Input is
12 articles, at most 3 per category, from the local calendar day's
`fetched_at` window — llama3.2:3b produced 19 label-only bullets from 20
inputs. The prompt gives the bullet shape as a **template, never an example
story**: with a concrete example the 3B model copied it into the briefing
verbatim as if it were news. The route claims the "generating" flag
synchronously (`try_claim`) before scheduling the task, so a GET right after
the POST already reports `generating` and double clicks can't start two.

## 4. Carry-overs from v0.3

- **react-router 6 -> 7 upgrade.** Two moderate advisories (open redirect via
  backslash in `<Link>`; constructor injection in `deserializeErrors()`)
  affect `react-router` 6.0.0-7.17.0 and are only fixed in 7.18+, which is a
  major migration. Neither is reachable in this app — there is no SSR, and
  link targets are the app's own routes — so `audit:prod` fails CI on
  high/critical only. Do the upgrade deliberately, not via `npm audit fix`.
- **Topics view has no per-article controls.** ArticleGroup renders only an
  expand button — no delete, save, or mark-read — while Cards/List/Sources/
  Timeline all use ArticleCard and have the full set. Topics is the default
  on every tab except Others, so a user who never switches views has no way
  to delete anything. Adding per-article controls inside a group is a design
  question (do they act on the representative article or the whole group?),
  which is why it was not patched in alongside the delete fixes.
- **Hourly weather scheduler** — observations are currently recorded when a
  forecast is viewed, which covers normal use but not a machine left idle.
- **Rebuild the desktop app** after any backend change:
  `./build-desktop-mac.sh`. The frozen sidecar does not pick up source edits.

**Decisions (2026-10-02):**

- react-router: upgrade to `react-router` 7 (the `-dom` package is folded
  in; imports change from `react-router-dom` to `react-router`). The app uses
  only `BrowserRouter/Routes/Route/Navigate/Link/Outlet` and the
  `useNavigate/useParams/useSearchParams/useLocation` hooks, all unchanged in
  v7's declarative mode. `npm audit --omit=dev` must then be clean.
  As built: 7.18.4 — 0 vulnerabilities. v8 (8.4.0) was already out; it is a
  separate migration, not needed for the advisories. After the install the
  Vite dev server must be restarted (stale optimized-deps cache → blank page).
- Topics: the note above is stale — `ArticleGroup` renders every article
  through `ArticleCard`, so each has its own delete/save/read controls,
  acting on that one article. **But verification found Topics never grouped
  at all** (see "Found and fixed" above): no page passed `groups`, and the
  refresh never created any. As built, `ArticleList` derives topic groups
  from the fetched page by `groupId` (so pagination and counts mean the
  same in every view), related sources start collapsed, and a group drops
  deleted members and disappears when its last article is deleted.
- Weather: an hourly interval job that, for each saved
  `WeatherLocation`, fetches current conditions and records an observation
  through the same path the forecast route uses. Best-effort per location.
  As built: `lib/scheduler/weather.py`, first run 60 s after startup, and it
  applies the observation/daily retention that was never being called.

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
- `bundle_dmg.sh` drives Finder through AppleScript and fails without
  automation permission (e.g. from a non-interactive shell), making
  `tauri build` exit non-zero *after* the `.app` is done. Under `set -e` that
  used to abort before the verification and the `install_file/` copy; the
  script now lets its own verification decide (v0.4).

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
