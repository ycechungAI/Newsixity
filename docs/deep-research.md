# Deep Research Setup

Deep Research lets you ask a question about any article; it searches the
web, fetches sources, and has Ollama synthesize a cited answer. It needs a
search engine to find sources — the **Brave Search API** (free tier) is
recommended, since anti-bot measures make scraping unreliable.

## Setup via Settings Page (recommended)

1. Get a free API key: [brave.com/search/api](https://brave.com/search/api/)
2. Open Newsixity → **Settings** (`/settings`)
3. Paste the key under **Brave Search API Key**, pick an **Ollama Model**,
   confirm **Ollama Host** (default `http://localhost:11434`)
4. Save. Settings are stored encrypted in SQLite (requires
   `NEWSIXITY_SETTINGS_ENCRYPTION_KEY` — see below).

## Alternative: environment variable

```bash
export BRAVE_SEARCH_API_KEY="your-api-key-here"
```

Settings-page values take priority over the environment variable when both are set.

## Fallback: DuckDuckGo HTML scraping

If no Brave API key is configured, searches fall back to scraping
DuckDuckGo's HTML endpoint (`backend/app/lib/research/search.py`). This has
no quota but is less reliable than the API.

## How it works

1. You ask a question about an article.
2. **Search**: Brave Search API, falling back to DuckDuckGo HTML.
3. **Fetch**: downloads the top result pages and extracts text (SSRF-guarded — see `docs/DEVELOPER_GUIDE.md` §7).
4. **Synthesize**: Ollama answers using only the fetched sources.
5. **Cite**: numbered citations `[1][2]` link back to sources.
6. **Cache**: saved to SQLite (`article_research` table) — asking the same question again is instant and doesn't use quota.

## Quota management

- Brave Search free tier: 2,000 queries/month.
- Newsixity tracks usage and stops issuing new API queries at **1,900/month** (`backend/app/db/repository/search_quota.py`, `MONTHLY_QUOTA_LIMIT`), resetting on the 1st.
- Cached results never count against quota.
- Ollama and content fetching have no built-in limit.

## Troubleshooting

**"The web search returned no results"**
- Check `BRAVE_SEARCH_API_KEY` is set correctly, or that DuckDuckGo isn't rate-limiting you.

**"Ollama is offline"**
```bash
ollama serve
curl http://localhost:11434
```

**Slow first search** — normal; it needs to search + fetch pages. Repeated identical questions are cached and instant.
