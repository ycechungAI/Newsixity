# Deep Research Feature Setup

The Deep Research feature requires a search engine to find sources. Due to anti-bot measures, we recommend using the **Brave Search API** (free tier).

## Setup via Settings Page (Recommended) ⚙️

The easiest way to configure Deep Research is through the built-in Settings page:

1. **Sign up for Brave Search API**:
   - Go to: https://brave.com/search/api/
   - Click "Get Started" or "Sign Up"
   - Get your API key from the dashboard

2. **Open Newsixity Settings**:
   - Click the ⚙️ Settings icon in the header
   - Or navigate to `/settings`

3. **Configure in Settings**:
   - **Brave Search API Key**: Paste your API key (it will be hidden after saving)
   - **Ollama Model**: Select from installed models or see suggestions
   - **Ollama Host**: Defaults to `http://localhost:11434`
   - Click "Save Settings"

4. **Done!** Your settings are stored securely in the local database.

## Alternative: Environment Variable

If you prefer environment variables:

1. Set the API key:
   ```bash
   export BRAVE_SEARCH_API_KEY="your-api-key-here"
   ```

2. Add to `~/.zshrc` or `~/.bashrc` to make permanent:
   ```bash
   echo 'export BRAVE_SEARCH_API_KEY="your-api-key-here"' >> ~/.zshrc
   source ~/.zshrc
   ```

3. Restart dev server:
   ```bash
   npm run dev
   ```

**Note**: Settings page values take priority over environment variables.

## Option 2: Web Scraping Fallback (Experimental)

If you don't set the API key, the system will attempt to scrape Bing search results. However, this may be unreliable due to anti-bot measures and rate limiting.

## Testing the Feature

1. Make sure Ollama is running: `ollama serve`
2. Open your Newsixity app
3. Find any article
4. Click the "Research" button
5. Type a question like "What are the latest developments?"
6. Wait for results (searches web → fetches content → AI synthesis)

## Troubleshooting

### "The web search returned no results"
- If using API: Check that `BRAVE_SEARCH_API_KEY` is set correctly
- If using scraping: Search engines may be blocking requests - use the API instead

### "Ollama is offline"
- Make sure Ollama is running: `ollama serve`
- Check it's accessible: `curl http://localhost:11434`

### Slow performance
- First search will be slower (needs to search + fetch pages)
- Subsequent identical questions are cached and instant

## How It Works

1. **User asks a question** about an article
2. **Search**: Queries Brave Search API (or scrapes Bing as fallback)
3. **Fetch**: Downloads top 5 result pages and extracts text
4. **Synthesize**: Ollama reads the sources and answers using only the provided information
5. **Cite**: Answer includes numbered citations [1][2] linking to sources
6. **Cache**: Result is saved to SQLite for instant retrieval next time

## Rate Limits & Quota Management

- **Brave Search API Free Tier**: 2,000 queries/month (~66/day)
- **Built-in Quota Protection**: Newsixity tracks usage and stops at 1,900 queries/month
- **Ollama**: No limits (runs locally)
- **Content Fetching**: No strict limits, but be respectful

### Quota Features

The app automatically tracks your monthly research queries:
- ✅ **Cached results don't count** - Ask the same question multiple times without using quota
- ⚠️ **Warning at 100 remaining** - Yellow banner shows when you're running low
- 🛑 **Stops at 1,900/2,000** - Prevents hitting API hard limit
- 🔄 **Resets monthly** - Counter resets on the 1st of each month

When quota is reached, you'll see: *"Monthly research quota reached (1900/month). The limit will reset at the beginning of next month. Cached questions still work!"*

For production use with higher volume, consider Brave Search's paid tiers or other search APIs.
