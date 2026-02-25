"use client";

import { useState, useEffect, useCallback } from "react";
import type { ResearchSource } from "@/types";

interface ResearchHistory {
  id: number;
  question: string;
  answer: string;
  sources: ResearchSource[];
  createdAt: string;
}

interface DeepResearchProps {
  articleId: number;
  articleTitle: string;
}

export default function DeepResearch({ articleId, articleTitle }: DeepResearchProps) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [sources, setSources] = useState<ResearchSource[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quotaRemaining, setQuotaRemaining] = useState<number | null>(null);
  const [history, setHistory] = useState<ResearchHistory[]>([]);

  const loadHistory = useCallback(async () => {
    try {
      const res = await fetch(`/api/research/history?articleId=${articleId}`);
      if (res.ok) {
        const data = await res.json();
        setHistory(data.history || []);
      }
    } catch (e) {
      console.error("Failed to load research history:", e);
    }
  }, [articleId]);

  // Load research history on mount
  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  const handleDeleteHistory = async (researchId: number) => {
    if (!confirm("Delete this research? This action cannot be undone.")) {
      return;
    }

    try {
      const res = await fetch(`/api/research/history?id=${researchId}`, {
        method: "DELETE",
      });

      if (res.ok) {
        // Remove from local state
        setHistory((prev) => prev.filter((item) => item.id !== researchId));
      } else {
        alert("Failed to delete research. Please try again.");
      }
    } catch (e) {
      console.error("Failed to delete research:", e);
      alert("Network error. Please try again.");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || loading) return;

    setLoading(true);
    setError(null);
    setAnswer(null);
    setSources([]);

    try {
      const res = await fetch("/api/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ articleId, question: question.trim() }),
      });

      if (!res.ok) {
        const data = await res.json();
        if (res.status === 429) {
          setError(
            "Monthly research quota reached (1900/month). The limit will reset at the beginning of next month. Cached questions still work!"
          );
        } else if (res.status === 503) {
          setError("Ollama is offline. Start Ollama to use Deep Research.");
        } else {
          setError(data.error || "Research failed");
        }
        return;
      }

      const data = await res.json();
      setAnswer(data.answer);
      setSources(data.sources || []);
      if (data.quotaRemaining !== undefined) {
        setQuotaRemaining(data.quotaRemaining);
      }

      // Reload history to show the new research
      void loadHistory();

      // Clear the question input after successful research
      setQuestion("");
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={`Ask about "${articleTitle.slice(0, 40)}..."`}
          className="flex-1 px-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-sky-500 text-white hover:bg-sky-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
        >
          {loading ? "Researching..." : "Search & Analyze"}
        </button>
      </form>

      {quotaRemaining !== null && quotaRemaining < 100 && (
        <div className="p-2 text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 rounded border border-amber-200 dark:border-amber-800">
          ⚠️ {quotaRemaining} research queries remaining this month
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
          <div className="w-4 h-4 border-2 border-sky-500 border-t-transparent rounded-full animate-spin" />
          <span>Searching the web and analyzing sources...</span>
        </div>
      )}

      {error && (
        <div className="p-3 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
          {error}
        </div>
      )}

      {answer && (
        <div className="space-y-3">
          <div className="p-3 text-sm text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-800/50 rounded-lg border-l-4 border-sky-500 whitespace-pre-wrap">
            {answer}
          </div>

          {sources.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                Sources
              </p>
              <ol className="space-y-1">
                {sources.map((source, i) => (
                  <li key={i} className="text-xs text-gray-500 dark:text-gray-400">
                    <span className="text-sky-500 font-medium">[{i + 1}]</span>{" "}
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sky-600 dark:text-sky-400 hover:underline"
                    >
                      {source.title || source.url}
                    </a>
                    {source.snippet && (
                      <span className="text-gray-400 dark:text-gray-500">
                        {" "}— {source.snippet.slice(0, 120)}...
                      </span>
                    )}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}

      {/* Research History */}
      {history.length > 0 && (
        <div className="mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">
            Research History ({history.length})
          </h3>
          <div className="space-y-4">
            {history.map((item) => (
              <div
                key={item.id}
                className="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700 group"
              >
                <div className="flex items-start justify-between mb-2">
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100 flex-1 pr-2">
                    {item.question}
                  </p>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">
                      {new Date(item.createdAt).toLocaleDateString()}
                    </span>
                    <button
                      onClick={() => handleDeleteHistory(item.id)}
                      className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-all"
                      title="Delete this research"
                    >
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>
                <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap mb-2">
                  {item.answer}
                </p>
                {item.sources.length > 0 && (
                  <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
                    <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                      Sources:
                    </p>
                    <ol className="space-y-0.5">
                      {item.sources.map((source, i) => (
                        <li key={i} className="text-xs text-gray-500 dark:text-gray-400">
                          <span className="text-sky-500 font-medium">[{i + 1}]</span>{" "}
                          <a
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sky-600 dark:text-sky-400 hover:underline"
                          >
                            {source.title || source.url}
                          </a>
                        </li>
                      ))}
                    </ol>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
