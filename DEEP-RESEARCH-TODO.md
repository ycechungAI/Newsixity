# Deep Research Feature — Implementation ✅ COMPLETE

Full plan with code snippets: `/Users/ycechung/.claude/plans/newsixity-deep-research.md`

## Completed Steps

- [x] **Step 1:** DB schema — Add `article_research` table to `src/lib/db/schema.ts`
- [x] **Step 2:** Types — Add `ResearchSource` + `ArticleResearch` interfaces to `src/types/index.ts`
- [x] **Step 3:** DB queries — Add `getArticleResearch`, `saveArticleResearch`, `getAllArticleResearch` to `src/lib/db/queries.ts`
- [x] **Step 4:** Web search — Create `src/lib/research/search.ts` (Brave Search API + Bing fallback)
- [x] **Step 5:** Research prompt — Add `RESEARCH_SYSTEM_PROMPT` to `src/lib/ollama/prompts.ts`
- [x] **Step 6:** Ollama research function — Create `src/lib/ollama/research.ts`
- [x] **Step 7:** Research orchestrator — Create `src/lib/research/orchestrator.ts`
- [x] **Step 8:** API endpoint — Create `src/app/api/research/route.ts`
- [x] **Step 9:** Modal component — Create `src/components/ui/Modal.tsx`
- [x] **Step 10:** DeepResearch component — Create `src/components/articles/DeepResearch.tsx`
- [x] **Step 11:** Wire into ArticleCard — Modified `src/components/articles/ArticleCard.tsx`
  - Added `ResearchIcon` SVG component
  - Added `showResearch` state
  - List view: research icon button + Modal with DeepResearch
  - Card view: Research button in action bar + collapsible DeepResearch panel
- [x] **Step 12:** Build verification — TypeScript passes with no errors

## Search Implementation Note

Due to anti-bot measures on search engines, the feature now uses:
1. **Primary**: Brave Search API (free tier: 2,000/month) - set `BRAVE_SEARCH_API_KEY`
2. **Fallback**: Bing web scraping (experimental, may be blocked)

**Setup instructions**: See `DEEP-RESEARCH-SETUP.md`

## Quick Start

1. Get Brave Search API key: https://brave.com/search/api/
2. Set environment variable: `export BRAVE_SEARCH_API_KEY="your-key"`
3. Restart dev server: `npm run dev`
4. Make sure Ollama is running: `ollama serve`
5. Click "Research" on any article!
