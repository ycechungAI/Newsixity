export interface SearchResult {
  url: string;
  title: string;
  snippet: string;
}

type BraveSearchResponse = {
  web?: {
    results?: Array<{
      url?: string;
      title?: string;
      description?: string;
    }>;
  };
};

/**
 * Search the web using Brave Search API (free tier: 2000/month).
 * Falls back to Bing scraping if no API key is set.
 *
 * To use Brave Search API (recommended):
 * 1. Sign up at https://brave.com/search/api/
 * 2. Add key in Settings page or set BRAVE_SEARCH_API_KEY environment variable
 */
export async function searchDuckDuckGo(
  query: string,
  maxResults: number = 8,
  apiKey?: string | null
): Promise<SearchResult[]> {
  // Use provided API key or fallback to environment variable
  const searchApiKey = apiKey || process.env.BRAVE_SEARCH_API_KEY;

  // Try Brave Search API first if key is available
  if (searchApiKey) {
    try {
      const response = await fetch(
        `https://api.search.brave.com/res/v1/web/search?q=${encodeURIComponent(query)}&count=${maxResults}`,
        {
          headers: {
            'Accept': 'application/json',
            'X-Subscription-Token': searchApiKey,
          },
        }
      );

      if (response.ok) {
        const data = await response.json() as BraveSearchResponse;
        const results: SearchResult[] = (data.web?.results || [])
          .filter((result) => result.url && result.title)
          .map((result) => ({
            url: result.url || "",
            title: result.title || "",
            snippet: result.description || "",
          }));

        console.log(`[Newsixity] Brave Search API found ${results.length} results for: ${query}`);
        return results;
      }
    } catch (e) {
      console.warn(`[Newsixity] Brave Search API failed, falling back to scraping: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  // Fallback: Scrape Bing with Playwright
  let browser;
  try {
    const { chromium } = await import("playwright-core");
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      userAgent:
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    });
    const page = await context.newPage();

    const searchUrl = `https://www.bing.com/search?q=${encodeURIComponent(query)}`;

    await page.goto(searchUrl, {
      waitUntil: "domcontentloaded",
      timeout: 30000,
    });

    await page.waitForTimeout(3000);

    const results = await page.evaluate((max: number) => {
      const items: { url: string; title: string; snippet: string }[] = [];

      // Try multiple Bing result selectors
      const resultElements = document.querySelectorAll('#b_results .b_algo, #b_results li.b_algo');

      for (const el of resultElements) {
        if (items.length >= max) break;

        const titleLink = el.querySelector('h2 a, a[href^="http"]') as HTMLAnchorElement | null;
        if (!titleLink) continue;

        const url = titleLink.href;
        const title = titleLink.textContent?.trim() || "";

        const snippetEl = el.querySelector('.b_caption p, .b_algoSlug, p');
        const snippet = snippetEl?.textContent?.trim() || "";

        if (!url || url.includes("bing.com/search") || !title) continue;

        items.push({ url, title, snippet });
      }

      return items;
    }, maxResults);

    await browser.close();

    if (results.length === 0) {
      console.warn(
        `[Newsixity] Bing scraping returned 0 results. Consider setting BRAVE_SEARCH_API_KEY env variable.`
      );
    } else {
      console.log(`[Newsixity] Bing scraping found ${results.length} results for: ${query}`);
    }

    return results;
  } catch (e) {
    console.warn(
      `[Newsixity] Web search failed: ${e instanceof Error ? e.message : String(e)}`
    );
    if (browser) await browser.close().catch(() => {});
    return [];
  }
}
