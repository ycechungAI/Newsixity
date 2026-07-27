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
  class as the bugs listed in §3.
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

## 3. Carry-overs from v0.3

- **Daily AI briefing** — planned, never built. Table + Ollama generation +
  cron + a `/briefing` page. Exclude Manual Links, matching
  `lib/scheduler/summarizer.py`.
- **Hourly weather scheduler** — observations are currently recorded when a
  forecast is viewed, which covers normal use but not a machine left idle.
- **Rebuild the desktop app** after any backend change:
  `./build-desktop-mac.sh`. The frozen sidecar does not pick up source edits.

## 4. The bug class to keep testing for

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

The reason these hide: **a missing API route returns 200 with the SPA's HTML**
via the static catch-all, so `res.ok` is true and only the JSON parse fails —
usually inside a `catch` that swallows it.

`backend/tests/integration/test_api_contract.py` now scans the frontend for
`fetch("/api/…")` calls and asserts each one exists with the right method. It
caught the Ollama one immediately. **Keep it passing, and prefer extending it
over adding narrow one-off tests** — it is the cheapest guard against this
whole class.

When adding a feature, verify the round trip end to end in the browser, not
just the unit. The user found four of these five by clicking; the tests should
be catching them first.
