# Stage 1b: Repository Layer Port — Complete

**Status:** ✅ Complete and verified against the real 109 MB production database.
**Haiku built:** Categories, Articles (reads/writes), Feeds, Article Groups, Stats
**Sonnet built:** Article Research, Search Quota, Settings (AES-256-GCM encryption),
Finance caches, Console (queue/culling/manual links), Ranking/Promotion, Preferences,
reset-failed-articles — plus review and bug-fixes across Haiku's draft (see below).

## Review Outcome (Sonnet 5)

Six real bugs were found in Haiku's draft while completing the remaining ~60% and
testing everything end-to-end. All were caught by actually *running* the code against
scratch and production databases, not just reading it — several were the kind of bug
that reads as plausible SQLAlchemy but silently does the wrong thing or crashes only
at call time.

1. **`article_groups.py` — invalid syntax, would crash at runtime.**
   `func.count(case=[(ArticleModel.is_read == 0, 1)])` uses SQLAlchemy 1.x's
   list-based `case()` as a kwarg to `func.count()` — not valid in SQLAlchemy 2.0.

2. **`article_groups.py` — wrong filter semantics.** The sports/promoted filters
   were applied against *any* article row joined into the query, but queries.ts's
   SQL filters via `EXISTS (... WHERE a_rep.id = ag.representative_id AND ...)` —
   i.e. against the group's **representative article specifically**. A group whose
   representative wasn't promoted but contained an unrelated promoted article would
   have been wrongly included. Fixed using `aliased(ArticleModel)` + correlated
   `EXISTS` subqueries, matching the original exactly — and eliminated the N+1 in
   the same pass (was 1+2N queries per call; now 3 regardless of group count),
   verified against real category/sports/promoted-filter data.

3. **`upsert_article` / `update_article_content` — dropped security hardening.**
   The Node version calls `parseHttpUrl()` (rejects non-http(s) and
   credential-bearing URLs — SSRF guard) and `stripHtml()` (stored-XSS guard) before
   ever touching the DB; this repo's own `To DO.md` documents both as previously
   fixed vulnerabilities. Haiku's port silently dropped both checks. Restored via
   `app/lib/utils/{url,sanitize}.py` (ported early, ahead of Stage 3, since Stage 1b
   depends on them for correctness). Also switched `upsert_article` from
   check-then-insert to atomic `INSERT ... ON CONFLICT DO NOTHING` — the original
   check-then-insert has a TOCTOU race under concurrent RSS-refresh writes that the
   Node version's `INSERT OR IGNORE` doesn't have.

4. **`get_all_feeds` — invalid Row attribute access, would crash.**
   `row.FeedModel.id` is not a valid way to pull an ORM entity out of a
   multi-column `select()` result in SQLAlchemy 2.0; fixed to `row[0].id`
   (the convention used correctly elsewhere in the codebase).

5. **Three spots assigned `func.datetime("now")` directly to an ORM instance
   attribute** (`feeds.update_feed_last_fetched`, `article_groups.
   update_group_representative`, `article_groups.increment_group_count`) instead of
   using an `UPDATE ... VALUES` statement. Assigning a SQL `ClauseElement` to a
   tracked ORM attribute has no defined flush behavior — it doesn't error, it just
   doesn't do what it looks like it does. All three rewritten as explicit `update()`
   statements (matching the pattern already used correctly elsewhere), and
   `increment_group_count`'s counter was switched to an atomic
   `article_count = article_count + 1` SQL expression instead of Python
   read-modify-write.

6. **Stage 1a's `models.py` was itself missing `sqlite_autoincrement=True`
   on all 12 tables.** `schema.ts` declares `INTEGER PRIMARY KEY AUTOINCREMENT`
   on every table; SQLAlchemy's per-column `autoincrement=True` is a logical flag
   only and does **not** emit that SQL keyword for SQLite. Without the table-level
   option, a freshly-created (non-production) database would silently let SQLite
   reuse a deleted row's rowid — confirmed by reproducing it (create → delete →
   create again returned the same id) before fixing. The existing 109 MB production
   DB is unaffected (it already has `AUTOINCREMENT` baked in from the original
   Node-created schema); this only mattered for new installs / test databases.

Every fix above was verified with an executable test against either a scratch
database or (for read-only checks) the real production database — not just visual
inspection.

## Follow-ups for later stages (not blocking)

- `app/lib/utils/{url,sanitize}.py` were pulled forward from Stage 3 because Stage 1b
  needed them for correctness. Stage 3 should treat these as already done and just
  add the remaining utils (`truncate`, `extract_image_from_html` are already ported
  too; check `date.ts`, `search.ts`, `video.ts`).
- `get_cached_quotes` batching (flagged as an N+1 candidate in Improvements.md §D)
  was fixed as part of this stage, not deferred — it's now a single `IN(...)` query.

## Module map (`backend/app/db/repository/`)

| Module | Covers |
|---|---|
| `helpers.py` | Shared dataclasses (`Article`, `Category`, `Feed`, `ArticleGroup`), `map_article_row()`, `ARTICLE_SELECT`, sports/priority constants |
| `categories.py` | `get_categories`, `get_category_by_slug` |
| `articles.py` | Article reads/writes, summarization-queue queries, `reset_failed_and_skipped_articles` |
| `feeds.py` | Feed CRUD |
| `article_groups.py` | Group CRUD + `get_article_groups_by_category` (batched, EXISTS-based filters) |
| `stats.py` | Category counts, feed seeding |
| `article_research.py` | Deep Research Q&A cache |
| `search_quota.py` | Monthly external-search quota tracking |
| `settings.py` | Key/value settings store with AES-256-GCM encryption |
| `finance.py` | Watchlist, quote/chart TTL caches, heatmap snapshots |
| `console.py` | Summarization queue, priority culling, manual-link articles |
| `ranking.py` | Relevance scoring, promotion, feed source weights |
| `preferences.py` | User keyword preference weights |

All 96 symbols are re-exported from `app/db/repository/__init__.py`.

## Verification performed

- Full package imports cleanly (`import app.db.repository`).
- Every module exercised with executable tests on a scratch DB (not just read-through),
  including edge cases: SSRF/XSS guards, encryption round-trip + missing-key error path,
  TTL expiry boundaries, culling priority order, promotion top-N selection, preference
  manual-vs-auto source precedence, AUTOINCREMENT id-reuse prevention.
- Read-only checks for every module re-run against the real 109 MB production database.

---

**Authored by:** Haiku 4.5 (initial draft) + Sonnet 5 (completion, review, fixes).
**Status:** Stage 1b complete. Next: Stage 2 (Pydantic schemas) to wire this layer into API routes.
