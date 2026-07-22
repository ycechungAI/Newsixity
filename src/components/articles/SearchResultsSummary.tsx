"use client";

import { Link } from "react-router-dom";

interface SearchResultsSummaryProps {
  results: Array<{
    id?: number;
    title: string;
    link: string;
  }>;
  query?: string;
}

interface SearchResultsSummaryProps {
  results: Array<{
    id?: number;
    title: string;
    link: string;
  }>;
  query?: string;
  fallbackLink?: string;
}

export default function SearchResultsSummary({
  results,
  query,
  fallbackLink,
}: SearchResultsSummaryProps) {
  if (!results || results.length === 0) {
    // Show fallback message if no results but we have a fallback link
    if (fallbackLink) {
      return (
        <div className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20 p-6">
          <p className="text-sm text-amber-700 dark:text-amber-400 mb-3">
            Could not extract search results. Click below to view on {query ? `"${query}"` : "the search engine"}:
          </p>
          <a
            href={fallbackLink}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors text-sm font-medium"
          >
            View on Google
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
      );
    }
    return null;
  }

  return (
    <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20 p-6">
      <h3 className="mb-4 text-base font-semibold text-gray-900 dark:text-gray-100">
        {query ? `Top ${results.length} Search Results for "${query}"` : `Top ${results.length} Results`}
      </h3>

      <ol className="space-y-2">
        {results.map((result, index) => (
          <li key={`${result.link}-${index}`} className="flex gap-3">
            <span className="flex-shrink-0 w-5 h-5 flex items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400 text-xs font-medium">
              {index + 1}
            </span>
            <div className="flex-1 min-w-0">
              {result.id ? (
                <Link
                  to={`/article/${result.id}`}
                  className="text-sky-600 dark:text-sky-400 hover:text-sky-700 dark:hover:text-sky-300 font-medium line-clamp-1"
                >
                  {result.title}
                </Link>
              ) : (
                <a
                  href={result.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sky-600 dark:text-sky-400 hover:text-sky-700 dark:hover:text-sky-300 font-medium line-clamp-1"
                >
                  {result.title}
                </a>
              )}
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
