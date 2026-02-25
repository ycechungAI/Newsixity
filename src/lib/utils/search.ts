export interface SearchEngineInfo {
  name: string;
  queryParam: string;
  domain: string;
}

const SEARCH_ENGINES: Record<string, SearchEngineInfo> = {
  google: { name: "Google", queryParam: "q", domain: "google.com" },
  bing: { name: "Bing", queryParam: "q", domain: "bing.com" },
  duckduckgo: { name: "DuckDuckGo", queryParam: "q", domain: "duckduckgo.com" },
  yahoo: { name: "Yahoo", queryParam: "p", domain: "search.yahoo.com" },
  baidu: { name: "Baidu", queryParam: "wd", domain: "baidu.com" },
  yandex: { name: "Yandex", queryParam: "text", domain: "yandex.com" },
};

export interface DetectedSearchEngine {
  engine: SearchEngineInfo;
  query: string;
}

/**
 * Detect if a URL is from a search engine and extract the query
 */
export function detectSearchEngine(url: string): DetectedSearchEngine | null {
  try {
    const urlObj = new URL(url);
    const hostname = urlObj.hostname.toLowerCase();

    for (const engine of Object.values(SEARCH_ENGINES)) {
      if (hostname.includes(engine.domain)) {
        const query = urlObj.searchParams.get(engine.queryParam);
        if (query) {
          return { engine, query: decodeURIComponent(query) };
        }
      }
    }

    return null;
  } catch {
    return null;
  }
}

/**
 * Check if a URL is a search engine URL
 */
export function isSearchEngineUrl(url: string): boolean {
  return detectSearchEngine(url) !== null;
}
