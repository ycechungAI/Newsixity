"use client";

import Link from "next/link";

interface SearchResultsSummaryProps {
  results: Array<{
    id?: number;
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
          <li key={`${result.link}-${index}`} className="flex gap-3">
            <span className="flex-shrink-0 w-5 h-5 flex items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400 text-xs font-medium">
              {index + 1}
            </span>
            <div className="flex-1 min-w-0">
              {result.id ? (
                <Link
                  href={`/article/${result.id}`}
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
