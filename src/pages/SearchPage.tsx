import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { Article } from "@/types";
import ArticleList from "@/components/articles/ArticleList";
import EmptyState from "@/components/ui/EmptyState";

/**
 * Full-text search results.
 *
 * Reads ?q= from the URL rather than holding the term in state, so a search
 * is linkable, survives a reload, and works with the back button. The
 * top-bar form navigates here.
 */
export default function SearchPage() {
  const [params] = useSearchParams();
  const query = (params.get("q") ?? "").trim();

  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!query) {
      setArticles([]);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    fetch(`/api/articles/search?q=${encodeURIComponent(query)}&limit=100`)
      .then((r) => {
        if (!r.ok) throw new Error(`Search failed (${r.status})`);
        return r.json();
      })
      .then((data) => {
        // A slow earlier request must not overwrite a newer query's results.
        if (!cancelled) setArticles(data.articles ?? []);
      })
      .catch(() => {
        if (!cancelled) setError("Search failed. Please try again.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [query]);

  return (
    <div>
      <div className="page-title">Search</div>
      <div className="page-sub">
        {query
          ? loading
            ? `Searching for "${query}"…`
            : `${articles.length} result${articles.length === 1 ? "" : "s"} for "${query}"`
          : "Type a search term above"}
      </div>

      {error && (
        <div style={{ color: "var(--danger, #e53e3e)", fontSize: 12, margin: "8px 0" }}>
          {error}
        </div>
      )}

      {!loading && query && articles.length === 0 && !error && (
        <EmptyState
          title="No matches"
          description={`Nothing found for "${query}". Search covers article titles, summaries, and full text.`}
        />
      )}

      {/* autoMarkRead off: scrolling a result list is not reading the
          articles, and silently marking them read would lose them from the
          unread views. */}
      {articles.length > 0 && (
        <ArticleList articles={articles} viewMode="cards" autoMarkRead={false} />
      )}
    </div>
  );
}
