# Newsixity v0.2 — Implementation Spec

Companion to `version0.2_update_todo.md`. That file is the checklist; this file
is the contract. Everything here was verified against the codebase at commit
`de452b2`. Line numbers are accurate as of that commit — re-grep if they drift.

**Read this section before writing any code.**

---

## 0. Ground rules

### Architecture as it actually is

The app was ported from Next.js to **FastAPI (Python) + Vite/React (TypeScript)**.
Ignore any doc in the repo root that describes Next.js, `src/app/api/*`,
`src/lib/db/*`, or `better-sqlite3` — those paths no longer exist. Authoritative
layout:

| Concern | Location |
|---|---|
| SQLAlchemy models | `backend/app/db/models.py` |
| Query layer | `backend/app/db/repository/*.py` |
| Pydantic schemas | `backend/app/schemas.py` |
| HTTP routes | `backend/app/routers/*.py` |
| Router registration | `backend/app/main.py:98-108` |
| Scheduled jobs | `backend/app/lib/scheduler/*.py` |
| DB bootstrap + seed | `backend/app/db/init_db.py` |
| React routes | `src/main.tsx:19-33` |
| Pages | `src/pages/*.tsx` |
| Components | `src/components/*` |

### Conventions to follow

- **Adding a router:** create `backend/app/routers/<name>.py` with a
  `router = APIRouter()`, then register it in `backend/app/main.py` alongside
  the existing block at line 98, using `prefix="/api"` and `tags=["<name>"]`.
  Copy the endpoint style from `backend/app/routers/feeds.py:18-33`.
- **Adding a page:** create `src/pages/<Name>Page.tsx`, import it in
  `src/main.tsx`, and add a `<Route>` inside the existing `<Route element={<App />}>`
  block (lines 20-33).
- **Boolean columns are `INTEGER` 0/1, not `Boolean`.** Timestamps are `TEXT`
  via `datetime('now')` server defaults, not `datetime`. This is deliberate
  parity with the original schema — see `backend/app/db/models.py:1-22`. New
  tables must match this style.
- **Every table sets `sqlite_autoincrement=True`** in `__table_args__`. Omitting
  it lets SQLite recycle deleted rowids. See `models.py:13-21` for why this bit.

### ⚠️ Migration gotcha — read carefully

`init_db()` uses `create_all`, which **creates missing tables but never alters
existing ones**. Consequences:

- New tables (podcasts) → created automatically. Fine.
- New index on an **existing** table (task 3.3 below) → **will NOT be applied to
  an existing database.** It only appears on a fresh DB. You must issue an
  explicit `CREATE INDEX IF NOT EXISTS` statement at startup.
- Users have live databases at `~/Library/Application Support/Newsixity/newsixity.db`
  (~6 MB, 630 articles as of writing). Never write a migration that drops or
  rebuilds an existing table.

### Definition of done for every task

1. `npm run tests` passes (lint → basic → security → database).
2. No change to behavior of existing categories, saved articles, or read state.
3. New user-facing strings are plain and consistent with existing copy.
4. If the task touches the DB, it works on **both** a fresh DB and an existing
   ~6 MB one. Test both.

---

## 0.1 Which model runs which task

Most of v0.2 is seed data and transcription from tables that are already written
out in this spec — that is Haiku 4.5 work. Four things are not: anything that
requires *deciding* rather than *transcribing*, anything touching security, the
audio player's lifecycle, and cross-component batching.

| Task | Model | Why |
|---|---|---|
| A.1 add category tuple | **Haiku** | One line, exact text given |
| A.2 seed security feeds | **Haiku** | Copy-paste pattern + `curl` gate |
| B.1 keyword list (paste) | **Haiku** | The list is written out verbatim below |
| B.1 false-positive triage | **Sonnet 5** | Judgment call + possible redesign |
| B.2 add sports feeds | **Haiku** | Same pattern as A.2 |
| C.1 schema | **Haiku** | Columns/indexes fully specified in tables |
| C.2 feedparser mapping | **Haiku** | Mapping table given; parser is unit-testable |
| C.3 routes (CRUD) | **Haiku** | 7 endpoints, all specified |
| C.3 SSRF integration | **Sonnet 5** | Must locate an unnamed helper; security-critical |
| C.4 page + list UI | **Haiku** | Standard fetch-and-render |
| C.4 audio player | **Sonnet 5** | Effect cleanup, throttling, resume state |
| D.1 batch mark-read | **Sonnet 5** | Shared queue across component instances |
| D.2 batch refresh fetch | **Haiku** | Local change, one query |
| D.3 compound index | **Haiku** | Steps given; escalate if `EXPLAIN` disagrees |
| D.4 doc triage | **Sonnet 5** → Haiku | Deciding what is still true needs code reading |
| D.5 CI artifact globs | **Haiku** | Five glob patterns |

### Where Haiku will go wrong if unsupervised

- **B.1** — Haiku will paste the keyword list and declare victory. It will not
  run the validation query, and it will not notice that `%canada%` drags
  political headlines into Sports. Either hand B.1 to Sonnet 5 whole, or have
  Haiku paste the list and stop, then review the false-positive output yourself.
- **C.3 SSRF** — the spec deliberately does not name the helper, because it must
  be found in the current code. Haiku will "solve" this by writing a plain
  `httpx.get`, which silently removes the protection. Sonnet 5 for this endpoint.
- **C.4 player** — `<audio>` plus React effects is the classic source of
  double-attached listeners, progress writes that never stop, and stale closures
  over `progress_seconds`. This is the one frontend file worth the stronger model.
- **D.1** — the naive fix is per-card debounce, which does not batch anything;
  real batching needs one module-level queue shared by every `ArticleCard`.
- **D.4** — Haiku cannot tell which of the nine stale docs still describes real
  behavior. Produce the keep/delete list with Sonnet 5 (or by hand) first; the
  deletion itself is then Haiku work.

### Escalation rule for whoever is running Haiku

Stop and hand off to Sonnet 5 rather than improvising if any of these happen:

1. A file or line number in this spec does not match what is on disk.
2. `npm run tests` fails for a reason not obviously caused by your own edit.
3. The task requires choosing between two designs — this spec is meant to have
   pre-made every such choice, so its absence means the spec is incomplete.
4. A DB change needs to run against an existing database and the outcome differs
   from a fresh one.

Never invent a file path, endpoint, or column that is not named in this spec.

---

## Phase A — Security / Hacker News tab

**Why first:** cheapest by a wide margin. `src/main.tsx:25` already routes
`category/:slug` to `CategoryPage`, and `CategoryPage` is generic over slug. So
a new category needs **no new page, no new route, and no new component** — it is
seed data plus a sidebar entry. Ship this first to validate the pipeline before
touching anything structural.

### A.1 — Add the category

In `backend/app/db/init_db.py`, `DEFAULT_CATEGORIES` (line 26) is a list of
`(name, slug, sort_order)` tuples. Add:

```python
("Security", "security", 9),
```

Pick `sort_order` so it lands where you want in the sidebar; existing categories
occupy 1-8 (`world-news`, `finance`, `gaming`, `technology`, `sports`,
`weather`, `top-news`, `others`).

**Existing-DB behavior — verified.** `init_db.py:78-84` loops over
`DEFAULT_CATEGORIES` on *every* startup using
`sqlite_insert(Category).values(...).on_conflict_do_nothing()`. So adding a
tuple backfills existing databases automatically on next launch. No migration
needed for this step.

### A.2 — Seed the feeds

Feeds live in the `feeds` table (`models.py:46`), keyed to `category_id`.

Use the **exact pattern already in `init_db.py:93-98`**, which seeds the Manual
Links feed:

```python
stmt = (
    sqlite_insert(Feed)
    .values(category_id=<category_id>, name=..., url=...)
    .on_conflict_do_nothing()
)
session.execute(stmt)
```

This is idempotent because `feeds.url` is `UNIQUE` (`models.py:54`), so it is
safe to run on every startup and will backfill existing databases.

Resolve `category_id` by slug first, the same way line 88-90 resolves `others`:

```python
security_id = session.execute(
    select(Category.id).where(Category.slug == "security")
).scalar_one_or_none()
```

Guard on `is not None` before inserting, as line 92 does.

Required source (explicitly requested):
- `https://databreaches.net/feed/`

Suggested additional sources — verify each returns valid RSS before adding:
- Krebs on Security — `https://krebsonsecurity.com/feed/`
- BleepingComputer — `https://www.bleepingcomputer.com/feed/`
- The Hacker News — `https://feeds.feedburner.com/TheHackersNews`
- Schneier on Security — `https://www.schneier.com/feed/atom/`
- Hacker News front page — `https://hnrss.org/frontpage`

**Validate before committing.** For each URL:

```bash
curl -sSL --max-time 15 -o /dev/null -w '%{http_code} %{content_type}\n' <URL>
```

Drop any that 404, redirect to HTML, or return a non-feed content type. Do not
add a feed you have not fetched successfully.

### A.3 — Acceptance criteria

- [ ] "Security" appears in the sidebar with a live unread count.
- [ ] `/category/security` renders articles after a feed refresh.
- [ ] Existing categories are unchanged in content and ordering.
- [ ] Works on a fresh DB **and** on an existing one.

---

## Phase B — Sports expansion

**Current state:** the `sports` category (id 5) has exactly 4 feeds — ESPN Top
Headlines, BBC Sport, CBS Sports, Bleacher Report. Coverage is broad-outlet but
US-centric, and the keyword filter is much narrower than the feeds.

### B.1 — Broaden `SPORTS_KEYWORDS`

`backend/app/db/repository/helpers.py:116-120` currently reads:

```python
SPORTS_KEYWORDS = (
    "%basketball%", "%Basketball%",
    "%NBA%", "%NCAA%",
    "%olympic%", "%Olympic%", "%Olympics%"
)
```

This is used by `stats.py:23` and `article_groups.py:161` in
`title.ilike(kw)` comparisons.

**Important:** `ilike` is already case-insensitive, so the
`%basketball%`/`%Basketball%` pairs are redundant. Collapse to one entry each.

Expand to cover the requested surface — tennis, world/international sport,
Olympics **and Paralympics**, World Cups, and Canadian athletes. Suggested set
(keep lowercase, one per concept):

```python
SPORTS_KEYWORDS = (
    # Existing
    "%basketball%", "%nba%", "%ncaa%",
    "%olympic%", "%paralympic%",
    # Tennis
    "%tennis%", "%atp %", "%wta %", "%wimbledon%",
    "%us open%", "%french open%", "%roland garros%", "%australian open%",
    # World cups / international
    "%world cup%", "%fifa%", "%uefa%", "%champions league%",
    "%commonwealth games%", "%pan am games%",
    # Other majors
    "%soccer%", "%football%", "%cricket%", "%rugby%",
    "%hockey%", "%nhl%", "%formula 1%", "%grand prix%",
    # Canada
    "%canada%", "%canadian%", "%team canada%",
)
```

⚠️ **Two risks a naive expansion will hit — handle both:**

1. **`%football%` and `%canada%` are ambiguous.** "Canada" matches political and
   business headlines; "football" matches both codes. These keywords are used to
   *classify* articles into sports, so over-broad terms will pull non-sports
   news into the sports surface. Before committing, run the query below against
   a real DB and eyeball the false-positive rate. If it is bad, gate the
   generic terms so they only apply to articles already in the sports category
   rather than using them to classify.

2. **Performance.** These become `OR`-ed `LIKE '%…%'` predicates
   (`or_(*[... ilike(kw) ...])`). Leading-wildcard `LIKE` cannot use an index, so
   cost is linear in keyword count × row count. Going from 7 to ~30 keywords
   roughly quadruples that scan on a 630-row-and-growing table. Measure before
   and after; if it regresses, precompute a `sport_tag` column at insert time
   instead of filtering by title on every read.

Validation query:

```bash
sqlite3 "$HOME/Library/Application Support/Newsixity/newsixity.db" \
  "select title from articles where lower(title) like '%canada%' limit 40;"
```

### B.2 — Add feeds

Add to the existing `sports` category (id 5) using the **same
`sqlite_insert(...).on_conflict_do_nothing()` pattern as A.2** — resolve the
category by slug `"sports"`, then insert. The four existing feeds are already
present and will be skipped by the conflict clause.

Cover: tennis (ATP/WTA), international/world sport, Olympics and Paralympics,
World Cup, and Canadian sport (e.g. CBC Sports, TSN, Sportsnet). Apply the same
`curl` validation as A.2 — do not add a feed you have not fetched successfully.

### B.3 — Acceptance criteria

- [ ] Sports surface shows tennis, soccer/World Cup, Olympic/Paralympic, and
      Canadian content — not just basketball.
- [ ] False-positive rate from `%canada%`/`%football%` was measured and is
      acceptable, or those terms were gated.
- [ ] Category page load time did not measurably regress.
- [ ] Redundant case-variant keywords removed.

---

## Phase C — Podcasts

**This is the largest feature in v0.2** — new tables, a new router, a new page,
and audio playback. Do **not** start it until Phases A and B are merged. Build
it in the sub-phase order below; each sub-phase should be independently
shippable and testable.

### C.1 — Schema

Three new tables in `backend/app/db/models.py`. Follow the existing style:
`INTEGER` 0/1 booleans, `TEXT` timestamps with `_NOW` server defaults,
`sqlite_autoincrement=True`.

**`podcast_feeds`**

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | autoincrement |
| `title` | TEXT NOT NULL | |
| `feed_url` | TEXT NOT NULL UNIQUE | matches `feeds.url` uniqueness |
| `site_url` | TEXT NULL | |
| `description` | TEXT NULL | |
| `image_url` | TEXT NULL | artwork |
| `author` | TEXT NULL | |
| `is_favorite` | INTEGER NOT NULL DEFAULT 0 | show-level favorite |
| `last_fetched_at` | TEXT NULL | mirrors `feeds` |
| `last_error` | TEXT NULL | mirrors `feeds` |
| `created_at` | TEXT NOT NULL DEFAULT now | |

**`podcast_episodes`**

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | autoincrement |
| `podcast_id` | INTEGER NOT NULL FK → `podcast_feeds.id` | |
| `guid` | TEXT NOT NULL | dedupe key, as `articles.guid` |
| `title` | TEXT NOT NULL | |
| `audio_url` | TEXT NOT NULL | enclosure URL |
| `duration_seconds` | INTEGER NULL | may be absent in feed |
| `published_at` | TEXT NULL | |
| `description` | TEXT NULL | |
| `is_favorite` | INTEGER NOT NULL DEFAULT 0 | episode-level favorite |
| `progress_seconds` | INTEGER NOT NULL DEFAULT 0 | resume point |
| `is_played` | INTEGER NOT NULL DEFAULT 0 | |
| `created_at` | TEXT NOT NULL DEFAULT now | |

Indexes: `idx_podcast_episodes_podcast_id` on `podcast_id`;
`UniqueConstraint(podcast_id, guid)` to make re-fetch idempotent;
`idx_podcast_episodes_published_at` on `published_at DESC`.

**Favorites are columns, not a third table.** The `version0.2_update_todo.md`
draft listed a `podcast_favorites` table — don't build it. Favorites are a
per-row boolean on a single-user local app; a join table adds cost with no
benefit. If multi-device sync arrives in v0.3, revisit.

### C.2 — Feed parsing

Podcast RSS is RSS 2.0 plus the `itunes:` namespace. The project already depends
on `feedparser`, which handles both — reuse it rather than adding a dependency.

Field mapping:

| Target | Source | Fallback |
|---|---|---|
| `audio_url` | `entry.enclosures[0].href` | **skip the entry** if absent |
| `duration_seconds` | `itunes:duration` | `NULL` |
| `image_url` | `itunes:image` → `image.href` | `NULL` |
| `guid` | `entry.id` / `entry.guid` | hash of `audio_url` |

`itunes:duration` appears as `"3600"`, `"60:00"`, **and** `"1:00:00"` in the
wild. Write one parser handling all three and unit-test it. Skip entries with no
enclosure — they are not playable.

### C.3 — API

New `backend/app/routers/podcasts.py`, registered in `main.py` after line 108.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/podcasts` | list subscriptions |
| POST | `/api/podcasts` | subscribe by feed URL |
| DELETE | `/api/podcasts/{id}` | unsubscribe (cascade episodes) |
| GET | `/api/podcasts/{id}/episodes` | episodes, paginated |
| PATCH | `/api/podcasts/{id}` | toggle show favorite |
| PATCH | `/api/podcasts/episodes/{id}` | favorite / progress / played |
| POST | `/api/podcasts/refresh` | re-fetch all subscribed |

**SSRF:** `POST /api/podcasts` takes a user-supplied URL and fetches it
server-side. Item 3 of `To DO.md` added SSRF protections for exactly this shape
of endpoint. **Reuse that existing helper — do not write new fetch logic.** Find
it before implementing (`grep -rn "ssrf\|private\|allowlist" backend/app/lib/`).

**Progress writes:** `PATCH .../episodes/{id}` will be called repeatedly during
playback. Throttle client-side to at most once per ~10s. Do not write on every
`timeupdate` event — that fires ~4×/second and will hammer SQLite.

### C.4 — Frontend

- `src/pages/PodcastsPage.tsx`, imported in `src/main.tsx`, route
  `<Route path="podcasts" element={<PodcastsPage />} />` inside the `<App />`
  block.
- Sidebar entry in `src/components/layout/Sidebar.tsx`.
- Player component in `src/components/podcasts/`.

Use the **native `<audio>` element**. The app runs in WKWebView (macOS),
WebView2 (Windows), and WebKitGTK (Linux) — all support `<audio>` with MP3.
Do not add an audio library.

⚠️ **Linux/WebKitGTK codec caveat:** WebKitGTK relies on system GStreamer
plugins. MP3 needs `gstreamer1.0-plugins-good`; some podcasts ship AAC/M4A,
needing `gstreamer1.0-plugins-bad`/`-ugly`. These are **not** in the Tauri
dependency list in `.github/workflows/desktop-build.yml`. Verify playback on
Linux early — if plugins are missing, audio fails silently or errors obscurely.
Document required packages in `docs/desktop.md` and consider adding them to the
`.deb` dependencies.

Player requirements: play/pause, seek, resume from `progress_seconds`, speed
control (1×, 1.25×, 1.5×, 2×), and persisting progress on pause/unmount.

### C.5 — Acceptance criteria

- [ ] Subscribe by URL, unsubscribe, list subscriptions.
- [ ] Episodes list with title, date, duration.
- [ ] Favorite a show and an episode; both persist across restart.
- [ ] Playback works on **macOS, Windows, and Linux** — verify all three.
- [ ] Progress persists and resumes; writes are throttled.
- [ ] Malformed feed shows an error without crashing the page.
- [ ] SSRF protection confirmed active on `POST /api/podcasts`.

---

## Phase D — Maintenance

Independent of A–C; can be done any time.

### D.1 — Batch "mark read"

`src/components/articles/ArticleCard.tsx:44-51` gives every card its own
`IntersectionObserver` firing a separate `PATCH /api/articles/{id}`. Batch into
one call. Requires a new bulk endpoint (e.g. `PATCH /api/articles` taking an id
array); keep the single-id route for other callers (lines 79, 100, 116).

### D.2 — Batch post-refresh fetch

`backend/app/lib/scheduler/refresh.py:154` runs `get_article_by_id(i)` once per
inserted id inside a generator. Replace with one `WHERE id IN (...)` query. Same
pattern at line 144.

### D.3 — Add the `(is_read, published_at)` index

`backend/app/db/models.py:11-12` documents this as deliberately deferred. Only
`is_saved` has a partial index (line 120), yet nearly every page load sorts
`ORDER BY is_read ASC, published_at DESC WHERE is_read = 0`.

**Re-read the migration gotcha in §0.** Adding the `Index(...)` to
`__table_args__` alone will silently do nothing on existing databases. Issue an
explicit `CREATE INDEX IF NOT EXISTS` at startup as well, and verify on a copy
of a real ~6 MB DB:

```sql
EXPLAIN QUERY PLAN
SELECT * FROM articles WHERE is_read = 0 ORDER BY is_read ASC, published_at DESC;
```

Confirm it reports index usage rather than `SCAN articles`.

### D.4 — Doc cleanup

Retire `To DO.md` (items 1-18 done; 20/22 fixed in migration; 24 obsolete;
19/21/23 carried into `version0.2_update_todo.md` and §D above).

Triage these root-level docs — several predate the FastAPI migration and
describe the Next.js architecture: `PLAN.md`, `BUGS.md`, `DEEP-RESEARCH-TODO.md`,
`DEEP-RESEARCH-SETUP.md`, `IMPLEMENTATION_SUMMARY.md`, `FINAL_BEHAVIOR.md`,
`BEHAVIOR_SUMMARY.md`, `BACKUP_SYSTEM.md`, `STARTUP.md`. Fold anything still
true into `docs/`, delete the rest.

### D.5 — CI artifact paths

`.github/workflows/desktop-build.yml` uploads all of
`src-tauri/target/release/bundle/`, so the Linux artifact is **803 MB** — it
includes the unpacked AppImage build tree, not just installers. Restore
per-installer globs (`**/*.dmg`, `**/*.msi`, `**/*.exe`, `**/*.deb`,
`**/*.AppImage`).

---

## Sequencing

```
A (security tab)  →  B (sports)  →  C (podcasts, C.1→C.5 in order)
D — any time, independent
```

A and B are mostly seed data over the existing RSS pipeline and should ship
quickly. C is the real engineering. D.3 is worth doing before C, since podcast
tables will add read load to the same database.

## Out of scope for v0.2

Episode transcription, transcript search, social sharing, multi-device sync,
and saved searches are v0.3. Do not build toward them.
