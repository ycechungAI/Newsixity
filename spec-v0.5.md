# Newsixity v0.5 — spec: ranking and feed selection

Written 2026-10-02 against the working tree at `d1d13d6` + the uncommitted
v0.5 groundwork. **This is a spec only — nothing here is implemented.**

Read `spec-v0.4.md` and `spec.md` first. The invariants they set (route
ordering, SSRF gate, no-Alembic migrations, WAL, all CSS in one file) still
apply.

## Why this exists

v0.4 shipped ranking that computes but does not visibly act, and feed selection
that is decided by accident rather than by design. Both were found while
diagnosing "world-news only shows Al Jazeera", which is the thread this spec
pulls on.

Four concrete defects, all verified against the running app on 2026-10-02:

1. **Ranking has no effect on order.** `relevance_score` is written by
   `score_articles_for_category` and read by exactly one query —
   `promote_top_articles`. Every article list orders by `published_at DESC`
   alone (`articles.py` lines 92, 213, 431, 682, 715, 753, 789). So a
   100-point score and a 0-point score are displayed identically, and the
   Settings copy "Higher weight → more likely to appear in top articles"
   describes a system that does nothing of the kind.
2. **The daily insert cap is first-come-first-served.** With
   `CATEGORY_DAILY_INSERT_CAP = 20` shared across a section, the first feed to
   be processed drains the whole budget and every other feed is skipped for the
   rest of the 24h window. Measured on the live database across every section:
   technology gave 64 of 80 articles to Ars Technica and 0 to five other feeds;
   sports gave all 80 to BBC Sport; world-news gave all 80 to Al Jazeera. All 27
   starved feeds had a current `last_fetched_at` and an empty `last_error` —
   they fetched successfully and were silently discarded. §2 replaces the
   per-section cap with per-feed caps (soft 5, hard 8) and a section-wide
   fairness floor.
3. **Feed weights are silently clamped and can be set to nothing.**
   `score_article` clamps to 0.5–2.0 while the API accepts 0.1–10.0, so a
   stored 4.0 scores identically to 2.0. Separately, `PATCH /api/feeds/weights`
   never checks the feed exists: the `UPDATE` matches zero rows and the route
   still returns `{"success": true}`.
4. **Feed Rankings hides most of the feed list.** `filteredFeeds`
   (`SettingsPage.tsx:93-95`) hard-codes `["finance", "gaming", "sports",
   "world-news"]` — the same four slugs as `CAPPED_CATEGORIES`. Since
   `init_db` seeds 6 of 10 default feeds under `security` and `technology`,
   those feeds can never be ranked. The whitelist is also the reason the UI text
   implies an effect that capped-category scoping does not deliver.

Fix (2) is mechanical and lives in `_run_feed_refresh_sync`; the groundwork for
it is already in the tree uncommitted. Fixes (1), (3), (4) are design and are
specified here.

---

## 0. Definition of done

`pytest backend/tests` green, `tsc --noEmit` at 0 errors, `npm run lint` clean
for `src/`, and each behaviour clicked through in the browser against a
populated database — including the multi-feed category case, which is the one
that reproduces the original bug.

- [x] §1 Ranking must actually order the feed
- [x] §2 Per-feed caps: soft 5, hard 8, and a 6th only once the whole section has 5
- [x] §3 Feed weights are honest about their range
- [x] §4 Feed Rankings covers every feed, not a hard-coded subset
- [x] §5 Per-category ranking settings, persisted
- [x] §6 Explainability — a visible reason for the order
- [x] §7 Regression suite for the whole selection path

**Deliberately left open — §1.4's default.** Ranking now *covers* every
category and the Settings › Ranking panel can turn a section on, but the
seeded `ranked` flag reproduces v0.4 (on for the five capped sections, off for
technology, security, top-news, others, weather). Flipping those defaults is
the open question in §9 ("Should `sort=relevance` become the default at all?")
and is the user's call, not this change's.

**§9 volume question, now answerable.** §2.1 removed the shared budget, so a
section stores ~5 × n_feeds articles/day. On the 41-feed install measured
2026-10-03 that is ~205/day against the old ~140 — and because §5 makes both
caps per-section and configurable, the ceiling is now a setting rather than a
hard-coded 20.

## 1. Ranking must order the feed

The headline change. Today scoring writes a column nothing reads.

**1.1 A sort mode on the article list.** `GET /api/articles` and every
variant that lists articles take `sort`:

- `relevance` — `relevance_score DESC, published_at DESC` (default for capped
  categories once a score exists; falls back to recency for articles with no
  score, so a newly inserted article is never stranded at the bottom)
- `recent` — today's `published_at DESC`, unchanged
- `source` — `feed_name ASC, published_at DESC`, for when you want one outlet's
  back catalogue together

`relevance` must fall back per-article, not per-list: order by
`CASE WHEN relevance_score IS NULL THEN 1 ELSE 0 END, relevance_score DESC,
published_at DESC`. A partially-scored list must not hide its unscored tail.

**1.2 Default to relevance, and say so.** For capped categories the default
becomes `relevance`. The UI exposes the choice in the existing list header
(next to the Topics/flat toggle) rather than in a new settings screen — this
is a per-view decision, not a preference.

**1.3 Scope promotion to what ranking can see.** `promote_top_articles` today
clears and re-promotes from the last 24h on every refresh, so a score computed
at insert time is recomputed against a moving window. Keep the daily limit,
but promote from the same window the list sorts over, and record *why* an
article is promoted (§6).

**1.4 Non-capped categories get scored too.** `top-news`, `technology`,
`security`, `weather`, `others` are currently never scored, which is why §4's
whitelist exists at all. Scoring them removes the special case: every feed
becomes rankable, and `CAPPED_CATEGORIES` keeps only its one real meaning —
"this category is ranked and promoted".

## 2. Per-feed daily caps with a fairness floor

The bug from the field report: one shared budget per section, many feeds
competing, one winner. Measured across every section, the same shape — one feed
took the entire budget while 27 others fetched successfully and stored nothing.

The fix drops the per-section cap entirely and bounds **each feed** instead, so
fairness is a property of the rule rather than an accident of ordering.

**2.1 Remove the per-section cap.** `CATEGORY_DAILY_INSERT_CAP` goes away.
There is no longer a budget for a section to exhaust, so no feed can be starved
by another no matter how the feeds are ordered. `get_category_articles_count_in_last_24h`
(`console.py:209`) loses its last caller and is deleted rather than left
orphaned.

**2.2 Soft cap 5, hard cap 8, per feed per 24h.**

| Limit | Value | Meaning |
|---|---|---|
| Soft cap | 5 | Free to insert up to 5 articles in a rolling 24h window |
| Hard cap | 8 | Absolute ceiling; no feed may ever exceed 8 in 24h |

Both count articles whose `fetched_at` is within the last 24h — the same
window `get_category_articles_count_in_last_24h` uses, so behaviour is
consistent with the cap being removed.

**2.3 Fairness floor — the 6th article is conditional.** A feed may insert its
6th, 7th or 8th article **only once every other enabled feed in its section has
at least 5**. In other words the soft cap is a floor for the whole section
before any feed is allowed a second helping.

This is the substantive part. It means a section with 8 busy feeds stores ~40
articles/day (5 each), while a section with 3 feeds stores up to 24 (8 each if
all three are that busy). Sections size themselves to their membership.

**2.4 How the floor is evaluated.** It is a per-section condition, so it must
be computed **once per refresh**, before the insert loop, not per feed:

- For each enabled feed in the section, count its articles in the last 24h.
- `section_covered` = every one of those counts is `>= 5`.
- While inserting, a feed at 5 may continue only if `section_covered` is true;
  a feed below 5 may always continue, up to the hard cap of 8.

Recomputing it inside the loop would make it flap: a feed that inserts its 5th
article would raise the section's floor mid-pass and starve the feeds that had
not yet had a turn.

**2.5 A new per-feed count query is required.** Only the category-level count
exists today. Add `get_feed_article_count_in_last_24h(feed_id)` beside it. One
query per feed per refresh is acceptable — feeds number in the tens, and the
refresh already fetches every feed over the network.

**2.6 Duplicates must not consume the feed's allowance.** Advancing past a
title-hash or fuzzy duplicate does not count against the soft or hard cap, or a
feed that republishes an old story every refresh starves itself. This is the
same rule as §2.2 in the previous draft, and it now matters more: with only 8
allowed articles per feed, losing two to duplicates is a quarter of its budget.

**2.7 Newly inserted titles join the dedup pool.** Two feeds carrying the same
story should not both land. Append inserted titles as title-only records
(`_TitleOnly` in `refresh.py`) rather than re-reading full `Article` rows.

**2.8 Report why a feed stopped.** The refresh response must distinguish "feed
had nothing new" from "feed was capped". Return per-feed counts and, for any
feed that hit a cap, which limit stopped it. Without this the §7 bug class
reappears in a new disguise — the user cannot tell a quiet feed from a
silenced one.

**2.9 Per-feed caps configurable and visible.** `FEED_DAILY_SOFT_CAP = 5` and
`FEED_DAILY_HARD_CAP = 8` replace the module constants, and both belong in the
§5 settings surface. `DAILY_ARTICLE_LIMIT` (§ promotion) is unaffected and
stays as it is; the two are different mechanisms and must not be conflated —
`DAILY_ARTICLE_LIMIT` bounds what ranking **promotes**, the feed caps bound what
the refresh **stores**.

`FINANCE_DAILY_INSERT_CAP = 20` remains exported and never read — delete it
alongside §2.1.

**2.10 Surface the cap instead of hiding it.** Per §2.8, report per-feed caps
from `POST /api/feeds/refresh` and show them in the feed manager and refresh
tooltip. Today a user cannot tell "nothing new" from "silenced by a cap".

## 3. Feed weights honest about their range

**3.1 Clamp on write, not on read.** The API accepts 0.1–10.0;
`score_article` clamps to 0.5–2.0. Clamp at the boundary in the schema so the
stored value is always what was scored, and widen the UI or the accepted range
deliberately — not silently. Prefer keeping 0.5–2.0 and rejecting outside it.

**3.2 Verify the feed exists.** `PATCH /api/feeds/weights` must 404 on an
unknown `feedId` instead of returning `success: true`. Currently a stale id
reports success and persists nothing.

**3.3 Honour `ProtectedFeedError`.** The Manual Links feed (`internal://manual`)
is protected from update and delete in `feeds.py`, but the weights route can
still change its weight. It should refuse, consistently.

**3.4 Surface failures.** `updateFeedWeight` only updates state when
`res.ok` and otherwise shows nothing — the select snaps back with no
explanation. Use `apiErrorMessage` and show a message, matching `FeedManager`'s
existing `msg` banner.

**3.5 Kill the `Number(1.0)` / `"1.0"` class of bug at the type boundary.**
The Normal preset silently displayed as Low because React matches `<select>`
values as strings and `String(1.0)` is `"1"`. The options and the formatter
should be driven from one shared constant list of `{value, label}` so the
label and the stored representation cannot drift apart again.

## 4. Feed Rankings covers every feed

**4.1 Drop the whitelist.** Show all enabled feeds, grouped by category, with
a category header. `filteredFeeds` goes away.

**4.2 Show feeds with no effect honestly.** Until §1.1 lands, a weight on a
non-capped category changes nothing. The UI must not imply otherwise: either
the ranking ships first, or the UI labels the control as applying to ranked
categories only. Prefer the former; ship them together.

**4.3 Count-based display.** "3 of 6 feeds in this category" per group, and
flag categories that aren't ranked at all.

## 5. Per-category ranking settings, persisted

New surface, replacing the module constants in §2.5.

**5.1 Settings model.** Per section: `feedSoftCap` (default 5), `feedHardCap`
(default 8), `promoteLimit` (default 20), `ranked` (bool), and the §6 score
weights. There is no per-section insert cap (§2.1).
Stored server-side. No migration framework exists, so follow the
`_add_column_if_missing` pattern in `init_db.py` — additive, idempotent, never
a table rebuild. **Do not touch any existing database file.**

**5.2 Where it lives.** A `ranking_settings` table keyed by category slug, with
one row per capped category written at seed time. Settings UI: a new
"Ranking" section, one row per category.

**5.3 Defaults must reproduce today's behaviour.** A fresh install with no
rows must score exactly as v0.4 does. This is the regression guard for §1.4.

**5.4 Weight sliders for the scorer.** Expose the five signals in
`score_article` — group size, preference match, source weight, recency, title
importance — as 0–100 sliders that must sum to 100. Default to today's
30/30/20/10/10. `scorer.py` currently hard-codes them as literals; they become
parameters with those defaults.

## 6. Explainability

A score nobody can interrogate gets ignored. Cheap to add while the plumbing is
open.

**6.1 Store the components.** `score_article` computes five parts and returns
their sum. Persist the parts, not just the total — a `relevance_score_parts`
JSON column, or five columns. JSON keeps schema churn low.

**6.2 Show it.** Hovering the score in `ArticleCard` lists the five
contributions and their percentages. An article ranked top because 40 points
came from being covered by five outlets is self-explaining.

**6.3 Explain the cap.** When §2 caps a feed, the UI says which limit stopped
it (soft 5 or hard 8), how many it stored, and when its 24h window resets.

## 7. Regression suite

The reason every item above shipped broken: nothing tested the selection path
end to end. `CAPPED_CATEGORIES` and the UI whitelist drifted apart silently,
and nothing noticed.

- [x] No feed exceeds the hard cap of 8 in a rolling 24h window
- [x] A feed is held at 5 until every other feed in its section has 5
- [x] Once the whole section has 5, feeds may insert a 6th up to the hard cap
- [x] Duplicates do not consume a feed's soft or hard cap allowance
- [x] A section of many feeds and a section of few feeds each behave correctly
- [x] The per-section cap and its query are fully removed — no orphan callers
- [x] Refresh reports which limit stopped each capped feed
- [x] Ranking actually changes `ORDER BY` on a real list response
- [x] `relevance` ordering degrades gracefully with partially scored data
- [x] Weight out of range is rejected at the boundary
- [x] Unknown `feedId` PATCH is 404, not `success: true`
- [x] Protected feed refuses a weight change
- [x] Every preset in §3.5 round-trips and renders the label it stores
- [x] Refresh reports `capped` when a section's budget is spent
- [x] Sections are independent — one section spending 30 does not reduce another's
- [x] Every enabled feed is reachable in Feed Rankings — no whitelist
- [x] Default settings reproduce v0.4 scores

One caveat on the "renders the label it stores" row: the round-trip and the
shared-constant invariant are pinned in `tests/integration/test_feed_weights.py`
(`TestWeightWriteHonesty`), but *rendering* is frontend-only and this repo has
no frontend test harness. `src/lib/ranking/weightPresets.ts` now feeds both the
`<option value>` and the `<select value>` from one `presetValue()`, so the
string mismatch that caused the original bug is no longer expressible.

## 8. Deliberately not in scope

- **Deleting or hiding non-promoted articles.** v0.3 disabled deletion and
  `docs/ranking.md` records why. Nothing here re-enables it; ranking changes
  order and badges only. The user must be able to see everything they fetched.
- **Replacing the cap with a full-quality mode.** No "fetch everything" toggle
  yet — it is a storage and dedup decision, not a ranking one.
- **Changing the insert cap's existence.** The per-*section* cap is removed
  (§2.1) and replaced by per-feed caps. There is still a ceiling — a hard cap
  of 8 per feed per 24h — it just sits one level down and applies per feed.
- **Keeping the per-section cap as a safety valve.** If total volume becomes a
  problem, §5 makes these configurable; a global ceiling is deliberately not
  reintroduced here because any shared budget re-creates the starvation.
- **Ranking across categories.** Scoring is per-category throughout and stays
  that way.

## 9. Open questions for the user

- **Per-feed caps mean total volume now scales with feed count.** With the
  per-section cap gone, a section stores roughly `5 × n_feeds` articles/day
  (up to `8 × n_feeds` once every feed is busy). Across 41 feeds that is
  ~205/day rather than the current ~140. Worth confirming the database growth
  is acceptable — it is the direct cost of fairness, and there is no longer a
  global ceiling to hold it down.
- **Should feeds with zero articles for N days be surfaced or auto-disabled?**
  Several default feeds may be permanently dead. That is a §4 follow-up.
- **Should `sort=relevance` become the default at all?** It is a real
  behaviour change: the feed will stop reading strictly newest-first.

## 9a. Follow-ups noted while building

Separate from the ranking work, collected here so they are not lost.

- **Progress bar for the full-text backfill.** The Console button
  (`POST /api/console/backfill-full-text`) runs one bounded batch and then stops,
  so repairing ~632 articles means clicking it ~25 times with no indication of
  overall progress. Wanted: a progress bar showing repaired / pending, with the
  remaining count, rather than a toast per batch. A running job with a
  pollable status endpoint would serve better than one request per batch —
  this is the same shape as §2.8's "report which limit stopped each feed".
- **Report articles that can never be repaired.** Paywalled sources
  (Financial Times, Bloomberg) and video links return nothing extractable, and
  `ensure_article_text` correctly refuses to overwrite good text with less. They
  are re-attempted on every run for no gain. They should eventually be marked so
  the pending count reflects only articles that can actually be fixed.
- **Sportsnet's empty `<link>` elements.** All 56 entries carry a
  whitespace-padded CDATA link that feedparser discards, so every insert is
  silently rejected by the SSRF gate. The URL is recoverable from `<comments>`.
  Separately, `upsert_article` dropping entries without surfacing the count is
  the same silent-failure class this spec keeps running into.

## 10. Sequence

§2 first — the reported bug, groundwork already in the tree. §3 and §4
together, since they are one UI honesty problem. §1 after those, as the
behavioural change. §5 last, because it makes the §2/§1 constants
configurable and should not be built before they settle. §6 opportunistically
while the scorer is open in §1.4.