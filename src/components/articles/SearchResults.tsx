"use client";

import { useEffect, useState } from "react";
import { detectSearchEngine } from "@/lib/utils/search";

interface SearchLink {
  title: string;
  url: string;
  description?: string;
}

interface SearchResultsProps {
  url: string;
  title?: string;
}

export default function SearchResults({ url, title }: SearchResultsProps) {
  const [results, setResults] = useState<SearchLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const searchInfo = detectSearchEngine(url);

  useEffect(() => {
    if (!searchInfo) {
      setLoading(false);
      setError("Could not parse search query");
      return;
    }

    // Attempt to fetch and parse search results
    const fetchResults = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await fetch(url, {
          headers: {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
          },
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch: ${response.status}`);
        }

        const html = await response.text();

        // Parse HTML to extract links
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, "text/html");

        const links: SearchLink[] = [];

        // Try to find search result links based on common patterns
        // This is a best-effort approach as search engines change their HTML structure
        const selectors = [
          'a[href^="http"]', // Direct links
          'div[data-sokoban-container] a', // Google's structure
          'div.g a', // Google's legacy structure
          'li.b_algo a', // Bing's structure
          'div.result a', // DuckDuckGo structure
        ];

        const linkElements = new Set<HTMLAnchorElement>();
        for (const selector of selectors) {
          doc.querySelectorAll(selector).forEach((el) => {
            if (el instanceof HTMLAnchorElement && linkElements.size < 10) {
              linkElements.add(el);
            }
          });
        }

        // Filter and format results
        linkElements.forEach((el) => {
          if (links.length >= 10) return;

          const href = el.getAttribute("href");
          const text = el.textContent?.trim();

          // Skip unwanted URLs and text
          if (
            !href ||
            !text ||
            text.length < 5 ||
            href.includes("/search") ||
            href.includes("/intl/") ||
            text.toLowerCase().includes("translated by")
          ) {
            return;
          }

          // Try to extract the actual URL from redirect URLs
          let actualUrl = href;
          try {
            const redirectMatch = href.match(/url=([^&]+)/);
            if (redirectMatch) {
              actualUrl = decodeURIComponent(redirectMatch[1]);
            }
          } catch {
            // Keep original URL if parsing fails
          }

          links.push({
            title: text,
            url: actualUrl,
            description: el.parentElement?.textContent?.substring(text.length, 200).trim(),
          });
        });

        if (links.length === 0) {
          setError("Could not extract search results from the page");
        } else {
          setResults(links);
        }
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to fetch search results. Search engine may block automated requests."
        );
      } finally {
        setLoading(false);
      }
    };

    fetchResults();
  }, [url, searchInfo]);

  if (loading) {
    return (
      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-6">
        <div className="flex items-center gap-3">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-500"></div>
          <p className="text-blue-700 dark:text-blue-400">
            Fetching results for "{searchInfo?.query}"...
          </p>
        </div>
      </div>
    );
  }

  if (!searchInfo) {
    return (
      <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6">
        <p className="text-red-700 dark:text-red-400">
          Could not parse search query from URL
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-6">
        <div className="flex items-center gap-3 mb-2">
          <span className="text-sm font-semibold text-gray-600 dark:text-gray-400">
            {searchInfo.engine.name} Search
          </span>
        </div>
        <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">
          "{searchInfo.query}"
        </h3>
        <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
          {results.length > 0
            ? `Top ${results.length} results`
            : "Search results could not be extracted"}
        </p>
      </div>

      {error && (
        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
          <p className="text-sm text-amber-700 dark:text-amber-400">
            <strong>Note:</strong> {error}
          </p>
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 mt-3 text-sm text-amber-600 dark:text-amber-400 hover:text-amber-700 dark:hover:text-amber-300"
          >
            View on {searchInfo.engine.name}
            <svg
              className="w-4 h-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
              />
            </svg>
          </a>
        </div>
      )}

      {results.length > 0 && (
        <div className="space-y-3">
          {results.map((result, index) => (
            <a
              key={index}
              href={result.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block group rounded-lg border border-gray-200 dark:border-gray-700 p-4 hover:border-sky-300 dark:hover:border-sky-600 hover:bg-sky-50 dark:hover:bg-sky-900/20 transition-colors"
            >
              <div className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400 text-sm font-medium">
                  {index + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <h4 className="font-medium text-gray-900 dark:text-gray-100 group-hover:text-sky-600 dark:group-hover:text-sky-400 line-clamp-2 transition-colors">
                    {result.title}
                  </h4>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 truncate">
                    {result.url}
                  </p>
                  {result.description && (
                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-2 line-clamp-2">
                      {result.description}
                    </p>
                  )}
                </div>
              </div>
            </a>
          ))}
        </div>
      )}

      {!error && results.length === 0 && !loading && (
        <div className="bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-700 rounded-lg p-6 text-center">
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            No results could be extracted from the search page.
          </p>
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 rounded-lg hover:bg-gray-800 dark:hover:bg-gray-200 transition-colors text-sm font-medium"
          >
            View Original Search
            <svg
              className="w-4 h-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
              />
            </svg>
          </a>
        </div>
      )}
    </div>
  );
}
