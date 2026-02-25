"use client";

import { useState, useEffect, useCallback } from "react";

interface ArticleSummaryProps {
  articleId: number;
  initialSummary: string | null;
}

export default function ArticleSummary({
  articleId,
  initialSummary,
}: ArticleSummaryProps) {
  const [summary, setSummary] = useState<string | null>(initialSummary);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generateSummary = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/summarize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ articleId }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        if (res.status === 503) {
          setError("AI summarizer is offline. Click to retry.");
        } else if (res.status === 400) {
          setError(data.error || "Article has no content to summarize.");
        } else {
          setError("Failed to generate summary. Click to retry.");
        }
        return;
      }

      const data = await res.json();
      if (data.summary) {
        setSummary(data.summary);
      } else {
        setError("No summary returned. Click to retry.");
      }
    } catch {
      setError("Network error. Click to retry.");
    } finally {
      setLoading(false);
    }
  }, [articleId]);

  // Auto-trigger on mount if no summary exists
  useEffect(() => {
    if (summary) return;
    generateSummary();
  }, [summary, generateSummary]);

  // Already has summary — show it
  if (summary) {
    return (
      <div className="mb-6 rounded-lg border-l-4 border-sky-500 bg-sky-50 dark:bg-sky-900/20 p-4">
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-sky-700 dark:text-sky-400">
          AI Summary
        </p>
        <p className="text-sm leading-relaxed text-sky-900 dark:text-sky-100">{summary}</p>
      </div>
    );
  }

  // Loading state
  if (loading) {
    return (
      <div className="mb-6 rounded-lg border-l-4 border-sky-300 dark:border-sky-600 bg-sky-50 dark:bg-sky-900/20 p-4 animate-pulse">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-sky-500 dark:text-sky-400">
          Generating AI Summary...
        </p>
        <div className="h-4 bg-sky-100 dark:bg-sky-800/40 rounded w-3/4 mb-2" />
        <div className="h-4 bg-sky-100 dark:bg-sky-800/40 rounded w-1/2" />
      </div>
    );
  }

  // Error state with retry
  if (error) {
    // Non-retryable errors (no content)
    if (error.includes("no content")) {
      return null;
    }

    return (
      <button
        onClick={generateSummary}
        className="mb-6 w-full text-left rounded-lg border-l-4 border-amber-400 dark:border-amber-500 bg-amber-50 dark:bg-amber-900/20 p-4 hover:bg-amber-100 dark:hover:bg-amber-900/30 transition-colors cursor-pointer"
      >
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400 mb-1">
          AI Summary
        </p>
        <p className="text-sm text-amber-800 dark:text-amber-300">{error}</p>
      </button>
    );
  }

  return null;
}
