# Bug Report — Newsixity

Found via full-repo review (`tsc`, `eslint`, and targeted manual/agent-assisted audits) on 2026-07-06.
All 6 confirmed bugs below were fixed the same day; see each section's **Status** line.

## Confirmed bugs

### 1. Dead code + wrong handler wired to the Resummarize button
**Status:** ✅ Fixed — closed `handleRemove`'s brace, removed the dead duplicate `handleResummarize`, and the surviving handler (which resets failed/skipped articles before resummarizing) is now the one wired to the button.

**File:** [src/app/console/page.tsx:57-100](src/app/console/page.tsx)

`handleRemove` is missing its closing brace, so the entire "reset failed/skipped articles, then resummarize" implementation (lines 67-99) ends up defined *inside* `handleRemove` as unreachable dead code. A second, simpler `handleResummarize` (lines 102-125) is declared at the component's top level and is the one actually bound to the button — it never calls `/api/console/resummarize-failed`, so failed/skipped articles never get reset.

Confirmed by:
- `tsc --noEmit`: `'err' is of type 'unknown'` inside the dead nested function
- `eslint`: `'handleResummarize' is defined but never used`

**Fix direction:** close `handleRemove` properly after its `catch`, delete the duplicate/dead `handleResummarize`, and make the surviving one call `/api/console/resummarize-failed` before `/api/summarize`.

---

### 2. Selected Ollama model is never actually saved
**Status:** ✅ Fixed — `getOllamaModelSetting`/`setOllamaModelSetting` now delegate to the existing, already-correct generic `settings` table (`getSetting`/`setSetting`) instead of misusing `user_preferences`; removed the now-redundant duplicate write in `settings/route.ts`.

**File:** [src/lib/db/queries.ts:1917-1928](src/lib/db/queries.ts)

```ts
export function setOllamaModelSetting(model: string): void {
  const db = getDb();
  db.prepare(
    `INSERT INTO user_preferences (category_slug, keyword, weight, source, updated_at)
     VALUES (?, ?, ?, ?, datetime('now'))
     ON CONFLICT(category_slug, keyword) DO UPDATE SET ...`
  ).run('__global__', 'ollama_model', 1.0, 'manual');
}
```

The `model` parameter is never passed to `.run()` — the function always writes the literal string `'ollama_model'` into the `keyword` column. `getOllamaModelSetting()` then reads that same literal back (`row.keyword`) instead of an actual model name.

**Impact:** changing the model in Settings has no effect; the "current model" shown in the UI is meaningless (always resolves to the literal `"ollama_model"` or the hardcoded default).

**Fix direction:** the actual model name needs its own column/value (e.g. store it in a dedicated `keyword` value like `model:granite4.1:8b` split into row-per-preference, or add a proper `settings` table column) rather than overloading `weight`/`keyword` meant for ranking preferences.

---

### 3. `ReferenceError` crash on `POST /api/settings`
**Status:** ✅ Fixed — added `import { parseHttpUrl } from "@/lib/utils/url";`.

**File:** [src/app/api/settings/route.ts:22](src/app/api/settings/route.ts)

`parseHttpUrl` is used inside a Zod `.refine()` but never imported. It's exported from [src/lib/utils/url.ts:1](src/lib/utils/url.ts).

```ts
.refine((value) => value === undefined || parseHttpUrl(value) !== null, {
  message: "ollama_host must be a valid http/https URL",
})
```

**Impact:** any `POST /api/settings` request that includes `ollama_host` throws a `ReferenceError`, returning a 500 instead of validating the URL.

**Fix direction:** `import { parseHttpUrl } from "@/lib/utils/url";`

---

### 4. Quota-exceeded (403) handling is unreachable
**Status:** ✅ Fixed — `processBatch` now rethrows `SessionLimitExceededError` (aborting the batch) instead of swallowing it into `processingErrors`, so the route's 403 branch is reachable.

**Files:** [src/lib/services/SummarizationService.ts:101-109](src/lib/services/SummarizationService.ts), [src/app/api/summarize/route.ts:79-90](src/app/api/summarize/route.ts)

`processBatch`'s per-article catch block swallows `SessionLimitExceededError` into `processingErrors` instead of rethrowing it:

```ts
} catch (e) {
  if (e instanceof SessionLimitExceededError) {
    processingErrors.push({ id: article.id, reason: "..." });
  } else if (e instanceof Error) {
    ...
  }
}
```

The route handler special-cases exactly this error to return a 403 "quota exceeded" response, but it can never fire since the error never escapes `processBatch`. (Also note `isQuotaExceeded` is hardcoded to `false` at `SummarizationService.ts:88`, so this whole code path is currently a no-op stub regardless.)

**Fix direction:** either rethrow `SessionLimitExceededError` out of `processBatch` (aborting the batch) and let the route catch it, or drop the dead 403 branch in the route until the quota check is real.

---

### 5. Duplicate/lost search-result articles on re-search
**Status:** ✅ Fixed — `guid` is now derived from a SHA-256 hash of the result's own URL (kept behind the `${parentUrlHash}-` prefix that `getSearchResults`' `LIKE` query relies on) instead of the loop index.

**File:** [src/lib/db/queries.ts:1606-1617](src/lib/db/queries.ts)

```ts
for (let i = 0; i < results.length; i++) {
  ...
  // Use parent hash + index for GUID (matches getSearchResults pattern)
  const guid = `${parentUrlHash}-${i}`;
  db.prepare(`INSERT OR IGNORE INTO articles (...) VALUES (...)`).run(feedId, guid, ...);
}
```

`guid` is built purely from `parentUrlHash` + loop index, not from the result's actual URL. `articles` has `UNIQUE(feed_id, guid)` ([src/lib/db/schema.ts:52](src/lib/db/schema.ts)), so re-running a search against the same parent URL a second time generates identical GUIDs at each index. `INSERT OR IGNORE` then silently drops any new/different result that lands on an already-used index, even though its URL differs from what's already stored.

**Fix direction:** derive `guid` from a hash of `result.url` (or `parentUrlHash + hash(result.url)`) instead of the positional index.

---

### 6. Source-weight ranking score doesn't match its own documented intent
**Status:** ✅ Fixed — replaced the single linear formula with a piecewise-linear mapping matching the comment (0.5→0, 1.0→10, 2.0→20 on the 20-point scale), verified numerically.

**File:** [src/lib/ranking/scorer.ts:82-83](src/lib/ranking/scorer.ts)

```ts
// Source weight score: 0.5 = 0, 1.0 = 0.5, 2.0 = 1.0
const sourceScore = (Math.min(Math.max(sourceWeight, 0.5), 2.0) - 0.5) / 1.5 * 20;
```

The comment states the mapping should give `1.0 → 0.5` (fraction of max), but the formula gives `(1.0 - 0.5) / 1.5 = 0.333`, not `0.5`. Neutral-weighted sources (the default `1.0` most feeds have) score `6.7/20` instead of the intended `10/20`, systematically underranking most articles relative to the documented design.

**Fix direction:** use a piecewise mapping matching the comment (e.g. `0.5–1.0 → 0–0.5` and `1.0–2.0 → 0.5–1.0` linearly) instead of one linear formula across the whole `0.5–2.0` range.

---

## Lower-severity / worth a look

- **[src/lib/db/queries.ts:1457-1470](src/lib/db/queries.ts)** (`cullUnsummarizedQueueToLimit`) — culls unsummarized articles one row at a time in a `while` loop (`LIMIT 1` re-queried each iteration) instead of a batch delete; correct but O(n) query round-trips for large queues.

## Ruled out after verification (false positives from initial automated sweep)

- "Race condition" in `WeatherDashboard` / `Sidebar` state updates — both use functional `setState` updates (`setX(prev => ...)`), so there's no stale-closure issue.
- "Infinite loop" in `src/lib/content/fetcher.ts`'s paragraph-extraction regex — correct idiomatic `regex.exec()` + `g`-flag loop; `lastIndex` advances automatically.
- "Date bug" in `src/lib/rss/parser.ts` using `Date.now()` as a fallback to `new Date(...)` — valid `Date` constructor overload (accepts both ISO string and epoch ms).
- "Race" in `src/lib/dedup/grouping.ts` — it re-queries the DB fresh on every loop iteration, so groups created earlier in the same batch are visible to later iterations.
- Unsafe-cast claim in `src/lib/finance/yahoo.ts` (`(x as T) || 'CLOSED'`) — works fine at runtime; TS casts are compile-time only, the `||` fallback still applies to the actual runtime value.
- SQL injection claim on `getSearchResults` LIKE pattern — uses parameterized `?` placeholders, not string interpolation; not exploitable.
