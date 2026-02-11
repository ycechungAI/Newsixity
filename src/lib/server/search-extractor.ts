import { detectSearchEngine } from "@/lib/utils/search";

export interface ExtractedSearchResult {
  title: string;
  url: string;
  description?: string;
}

/**
 * Extract search results from a search engine URL
 * Attempts to fetch and parse the search results page
 */
export async function extractSearchResults(url: string): Promise<ExtractedSearchResult[]> {
  const searchInfo = detectSearchEngine(url);
  if (!searchInfo) {
    return [];
  }

  try {
    console.log("[Search Extractor] Fetching:", url);
    const response = await fetch(url, {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      },
      signal: AbortSignal.timeout(10000),
    });

    if (!response.ok) {
      console.error(`[Search Extractor] Failed to fetch search results: ${response.status}`);
      return [];
    }

    const html = await response.text();
    console.log("[Search Extractor] Received", html.length, "bytes");
    const results = parseSearchResults(html);
    console.log("[Search Extractor] Parsed", results.length, "results");

    // Return top 10 unique results
    return results.slice(0, 10);
  } catch (error) {
    console.error("[Search Extractor] Error extracting search results:", error);
    return [];
  }
}

/**
 * Parse HTML to extract search results using regex patterns
 * Works for most search engines
 */
function parseSearchResults(html: string): ExtractedSearchResult[] {
  const results: ExtractedSearchResult[] = [];
  const seenUrls = new Set<string>();

  try {
    // Extract all href links and their text
    const linkRegex = /<a[^>]+href=["']([^"']+)["'][^>]*>([^<]+)<\/a>/gi;
    let match;
    let linkCount = 0;
    let totalLinksFound = 0;

    // Count total links first
    const testRegex = /<a[^>]+href/gi;
    const allMatches = html.match(testRegex);
    totalLinksFound = allMatches ? allMatches.length : 0;
    console.log("[Parser] Total <a> tags found:", totalLinksFound);

    while ((match = linkRegex.exec(html)) && results.length < 10) {
      linkCount++;
      try {
        let href = match[1];
        let text = match[2]?.trim() || "";

        // Skip empty text
        if (!text || text.length < 3) {
          continue;
        }

        // Extract actual URL from redirect URLs FIRST (Google style)
        const redirectMatch = href.match(/[?&]url=([^&]+)/);
        if (redirectMatch) {
          try {
            href = decodeURIComponent(redirectMatch[1]);
          } catch {
            // Keep original if decoding fails
          }
        }

        // Skip navigation links and Google UI elements
        if (
          href.includes("/search") ||
          href.includes("/intl/") ||
          href.includes("/preferences") ||
          href.includes("/maps") ||
          href.includes("/advanced_search") ||
          href.includes("/support") ||
          href.startsWith("javascript:") ||
          href.startsWith("#")
        ) {
          continue;
        }

        // Validate URL
        if (!href.startsWith("http://") && !href.startsWith("https://")) {
          continue;
        }

        try {
          new URL(href);
        } catch {
          continue;
        }

        // Skip duplicates
        if (seenUrls.has(href)) continue;

        // Skip unwanted text and special sections
        if (
          text.toLowerCase().includes("translated by") ||
          text.toLowerCase().includes("cached") ||
          text.toLowerCase().includes("people also ask") ||
          text.toLowerCase().includes("related searches") ||
          text.toLowerCase().includes("more results") ||
          text.toLowerCase().includes("about this result") ||
          text.match(/^[\d›•\-\s]+$/) // Skip breadcrumb numbers/symbols
        ) {
          continue;
        }

        seenUrls.add(href);

        results.push({
          title: text,
          url: href,
          description: undefined,
        });
      } catch {
        // Skip individual parse errors and continue
        continue;
      }
    }
  } catch (error) {
    console.error("Error parsing search results HTML:", error);
  }

  return results;
}
