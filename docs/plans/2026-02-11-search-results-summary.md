# Search Results Summary Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Display the top 5 search result links in a simple numbered list on article pages when search engine URLs are added as manual links.

**Architecture:** When a search engine URL is added via the manual article API, the server extracts the top 10 results and saves them as articles. On the article detail page, we'll query those results and display the first 5 in a minimal numbered list below the embedded content. This reuses the existing extraction pipeline and provides a clean, simple interface for viewing results.

**Tech Stack:** Next.js, React, SQLite queries, TypeScript

---

## Task 1: Add Query Function for Search Results

**Files:**
- Modify: `/Users/ycechung/dev/Newsixity/src/lib/db/queries.ts`

**Step 1: Write the failing test**

Create a test to verify the query works. Open a Node REPL and test manually:

```bash
node
> const { getSearchResults } = require('./src/lib/db/queries');
> const results = getSearchResults("https://www.google.com/search?q=test");
> console.log(results);
```

Expected: Error or empty array (function doesn't exist yet)

**Step 2: Add the query function to queries.ts**

At the end of `/Users/ycechung/dev/Newsixity/src/lib/db/queries.ts` (after line ~1150), add:

```typescript
export function getSearchResults(articleUrl: string): Article[] {
  const db = getDb();
  const feedId = getManualLinksFeedId();

  if (!feedId) {
    return [];
  }

  // Generate the parent GUID the same way as createManualArticle
  import { createHash } from "crypto";
  const urlHash = createHash("sha256").update(articleUrl).digest("hex");
  const parentGuid = `manual-${urlHash.slice(0, 32)}`;

  // Find the parent article
  const parentArticle = db
    .prepare(
      `SELECT id FROM articles
       WHERE feed_id = ? AND guid = ?`
    )
    .get(feedId, parentGuid) as { id: number } | undefined;

  if (!parentArticle) {
    return [];
  }

  // Get articles that were created from this search
  // These are identified by having a guid starting with the parent's URL hash
  const results = db
    .prepare(
      `SELECT id, feed_id, guid, title, link, author, published_at, content, image_url, summary, is_read, is_saved
       FROM articles
       WHERE feed_id = ? AND guid LIKE ?
       AND guid != ?
       LIMIT 5`
    )
    .all(feedId, `${urlHash.slice(0, 32)}-%`, parentGuid) as Article[];

  return results.map((row) => ({
    ...row,
    feedName: "Manual Links",
    categorySlug: "others",
  }));
}
```

**Step 3: Test the function**

```bash
node
> const { getSearchResults } = require('./dist/lib/db/queries');
> const results = getSearchResults("https://www.google.com/search?q=test");
> console.log(results.length); // Should be 0-5
```

Expected: Returns array of Article objects (empty if no results exist)

**Step 4: Commit**

```bash
git add src/lib/db/queries.ts
git commit -m "feat: add getSearchResults query function"
```

---

## Task 2: Create SearchResultsSummary Component

**Files:**
- Create: `/Users/ycechung/dev/Newsixity/src/components/articles/SearchResultsSummary.tsx`

**Step 1: Write the component**

Create `/Users/ycechung/dev/Newsixity/src/components/articles/SearchResultsSummary.tsx`:

```typescript
"use client";

import Link from "next/link";

interface SearchResultsSummaryProps {
  results: Array<{
    id: number;
    title: string;
    link: string;
  }>;
  query?: string;
}

export default function SearchResultsSummary({
  results,
  query,
}: SearchResultsSummaryProps) {
  if (!results || results.length === 0) {
    return null;
  }

  return (
    <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20 p-6">
      <h3 className="mb-4 text-base font-semibold text-gray-900 dark:text-gray-100">
        {query ? `Top ${results.length} Search Results for "${query}"` : `Top ${results.length} Results`}
      </h3>

      <ol className="space-y-2">
        {results.map((result, index) => (
          <li key={result.id} className="flex gap-3">
            <span className="flex-shrink-0 w-5 h-5 flex items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400 text-xs font-medium">
              {index + 1}
            </span>
            <div className="flex-1 min-w-0">
              <Link
                href={`/article/${result.id}`}
                className="text-sky-600 dark:text-sky-400 hover:text-sky-700 dark:hover:text-sky-300 font-medium line-clamp-1"
              >
                {result.title}
              </Link>
              <p className="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">
                {result.link}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
```

**Step 2: Verify component compiles**

```bash
cd /Users/ycechung/dev/Newsixity
npm run build 2>&1 | grep -i "searchresultssummary" || echo "No errors"
```

Expected: No TypeScript errors for the new component

**Step 3: Commit**

```bash
git add src/components/articles/SearchResultsSummary.tsx
git commit -m "feat: create SearchResultsSummary component"
```

---

## Task 3: Update Article Detail Page

**Files:**
- Modify: `/Users/ycechung/dev/Newsixity/src/app/article/[id]/page.tsx`

**Step 1: Add import**

At the top of the file (after line 10), add:

```typescript
import { getSearchResults } from "@/lib/db/queries";
import SearchResultsSummary from "@/components/articles/SearchResultsSummary";
```

**Step 2: Add query and extract search info**

After line 60 (after `markArticleRead(articleId);`), add:

```typescript
  // Get search results if this is a search engine article
  let searchResults = null;
  let searchQuery = null;

  if (article.feedName === "Manual Links" && isSearchEngineUrl(article.link)) {
    const results = getSearchResults(article.link);
    if (results.length > 0) {
      searchResults = results;
      // Extract query from URL for display
      const searchInfo = detectSearchEngine(article.link);
      searchQuery = searchInfo?.query || undefined;
    }
  }
```

You'll need to add the import for `detectSearchEngine`:

```typescript
import { detectSearchEngine } from "@/lib/utils/search";
```

**Step 3: Remove SearchResults component usage**

Find the section around line 113-125 that shows:

```typescript
{article.feedName === "Manual Links" && article.link && (
  <div className="mb-8">
    {isVideoUrl(article.link) ? (
      <VideoEmbed url={article.link} title={article.title} />
    ) : isSearchEngineUrl(article.link) ? (
      <SearchResults url={article.link} title={article.title} />
    ) : (
      <WebPageEmbed url={article.link} title={article.title} />
    )}
  </div>
)}
```

Replace it with:

```typescript
{article.feedName === "Manual Links" && article.link && (
  <div className="mb-8">
    {isVideoUrl(article.link) ? (
      <VideoEmbed url={article.link} title={article.title} />
    ) : !isSearchEngineUrl(article.link) ? (
      <WebPageEmbed url={article.link} title={article.title} />
    ) : null}
  </div>
)}
```

**Step 4: Add SearchResultsSummary below embedded content**

After the embedded content section (after line 125, before the AI Summary section), add:

```typescript
        {/* Search Results Summary */}
        {searchResults && searchResults.length > 0 && (
          <div className="mb-8">
            <SearchResultsSummary results={searchResults} query={searchQuery} />
          </div>
        )}
```

**Step 5: Remove old SearchResults import**

At the top of the file, remove this line:

```typescript
import SearchResults from "@/components/articles/SearchResults";
```

**Step 6: Verify changes**

```bash
cd /Users/ycechung/dev/Newsixity
npm run build
```

Expected: Build succeeds with no errors

**Step 7: Commit**

```bash
git add src/app/article/[id]/page.tsx
git commit -m "feat: integrate SearchResultsSummary on article page"
```

---

## Task 4: Manual Testing

**Step 1: Start dev server**

```bash
cd /Users/ycechung/dev/Newsixity
npm run dev
```

Expected: Dev server starts on localhost:3001

**Step 2: Test with a search URL**

1. Navigate to http://localhost:3001
2. Go to "Others" category
3. Click "Add Link" button
4. Enter:
   - URL: `https://www.google.com/search?q=artificial+intelligence+news`
   - Title: `AI News Search`
   - Content: (optional)
5. Click "Add Link"
6. Wait for the page to reload
7. Click on the newly created article card titled "AI News Search"
8. Verify: On the article page, you should see a blue box with "Top X Search Results for 'artificial intelligence news'" and a numbered list of links

**Step 3: Verify article links work**

1. In the search results summary, click on one of the numbered result links
2. Expected: Should navigate to that article's detail page
3. Verify the article displays correctly

**Step 4: Test with different search engine**

1. Repeat steps 2-3 with a Bing URL: `https://www.bing.com/search?q=machine+learning`
2. Verify results display

**Step 5: Test with no results**

1. Add a search URL that won't have extracted results (edge case)
2. Verify the component gracefully doesn't display anything

---

## Task 5: Commit Summary

```bash
git log --oneline -5
```

Expected output should show:
- feat: integrate SearchResultsSummary on article page
- feat: create SearchResultsSummary component
- feat: add getSearchResults query function

---

## Verification Checklist

- [ ] Search results summary appears on article pages for search engine URLs
- [ ] Shows exactly 5 or fewer results (numbered 1-5)
- [ ] Clicking result links navigates to article pages
- [ ] Component handles missing results gracefully (doesn't show)
- [ ] Works with Google, Bing, DuckDuckGo (based on existing extraction)
- [ ] Build succeeds with no TypeScript errors
- [ ] Three clean commits with descriptive messages

---

## Rollback Plan

If issues arise:

```bash
# Revert the three commits
git revert HEAD~2..HEAD

# Or reset to before this work
git reset --hard <commit-before-task-1>
```

---

## Notes

- The existing `SearchResults.tsx` component is left in place (not deleted) for potential future use
- Search result extraction happens automatically in the API when a search URL is added
- No database schema changes needed
- No new dependencies required
