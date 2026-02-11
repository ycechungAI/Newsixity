import { detectSearchEngine } from "@/lib/utils/search";

export interface ExtractedSearchResult {
  title: string;
  url: string;
  description?: string;
}

/**
 * Extract search results for a search engine URL.
 * Uses DuckDuckGo's HTML endpoint as the extraction backend since
 * Google/Bing render results with JavaScript (unscrapable from server).
 */
export async function extractSearchResults(url: string): Promise<ExtractedSearchResult[]> {
  const searchInfo = detectSearchEngine(url);
  if (!searchInfo) {
    return [];
  }

  try {
    // Use DuckDuckGo HTML endpoint — it returns real links in static HTML
    const ddgUrl = `https://html.duckduckgo.com/html/?q=${encodeURIComponent(searchInfo.query)}`;

    const response = await fetch(ddgUrl, {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      },
      signal: AbortSignal.timeout(10000),
    });

    if (!response.ok) {
      return [];
    }

    const html = await response.text();
    return parseDuckDuckGoResults(html).slice(0, 5);
  } catch (error) {
    console.error("[Search Extractor] Error:", error);
    return [];
  }
}

/**
 * Parse DuckDuckGo HTML results page.
 * DDG uses class="result__a" for result title links and
 * wraps actual URLs in //duckduckgo.com/l/?uddg=<encoded-url>
 */
function parseDuckDuckGoResults(html: string): ExtractedSearchResult[] {
  const results: ExtractedSearchResult[] = [];
  const seenUrls = new Set<string>();

  // Match result blocks: <a class="result__a" href="...">title</a>
  const resultRegex = /<a[^>]+class=["']result__a["'][^>]+href=["']([^"']+)["'][^>]*>([^<]+)<\/a>/gi;
  let match;

  while ((match = resultRegex.exec(html)) && results.length < 10) {
    const rawHref = match[1];
    const title = match[2]?.trim();

    if (!title || title.length < 3) continue;

    // Extract actual URL from DuckDuckGo redirect
    let actualUrl = rawHref;
    const uddgMatch = rawHref.match(/uddg=([^&]+)/);
    if (uddgMatch) {
      try {
        actualUrl = decodeURIComponent(uddgMatch[1]);
      } catch {
        continue;
      }
    }

    // Must be a real http(s) URL, skip DDG ad redirects
    if (!actualUrl.startsWith("http://") && !actualUrl.startsWith("https://")) {
      continue;
    }
    if (actualUrl.includes("duckduckgo.com/y.js") || actualUrl.includes("bing.com/aclick")) {
      continue;
    }

    // Skip duplicates
    if (seenUrls.has(actualUrl)) continue;
    seenUrls.add(actualUrl);

    // Extract description if available (appears in result__snippet)
    let description: string | undefined;
    const snippetAfter = html.slice(match.index, match.index + 1000);
    const snippetMatch = snippetAfter.match(/class=["']result__snippet["'][^>]*>([^<]+)</);
    if (snippetMatch) {
      description = snippetMatch[1].trim();
    }

    results.push({ title, url: actualUrl, description });
  }

  return results;
}
