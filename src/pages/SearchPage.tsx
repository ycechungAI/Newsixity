import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import type { Article } from "@/types";
import ArticleList from "@/components/articles/ArticleList";
import EmptyState from "@/components/ui/EmptyState";

interface SearchLink {
  name: string;
  template: string;
}

interface RemoteResult {
  title: string;
  url: string;
  source: string;
  discussionUrl: string | null;
  points: number | null;
  comments: number | null;
}

interface CategoryOption {
  slug: string;
  name: string;
}

const FILTER_KEYS = ["category", "from", "to", "saved"] as const;

/**
 * Full-text search results.
 *
 * Every input — the term and the filters — lives in the URL rather than in
 * state, so a search is linkable, survives a reload, and works with the back
 * button. The top-bar form navigates here; category pages link here with
 * ?category= preset.
 */
export default function SearchPage() {
  const [params, setParams] = useSearchParams();
  const query = (params.get("q") ?? "").trim();
  const category = params.get("category") ?? "";
  const from = params.get("from") ?? "";
  const to = params.get("to") ?? "";
  const saved = params.get("saved") === "1";

  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  const [links, setLinks] = useState<SearchLink[]>([]);
  const [remote, setRemote] = useState<{ results: RemoteResult[]; error: string | null } | null>(null);

  // Remove a deleted article from this list immediately. ArticleCard hides
  // its own instance, but the same article can be on screen in another view
  // (and in the sidebar counts) — leaving it there reads as "delete did
  // nothing".
  useEffect(() => {
    const onDeleted = (e: Event) => {
      const id = (e as CustomEvent<{ id: number }>).detail?.id;
      if (id == null) return;
      setArticles((prev) => prev.filter((a) => a.id !== id));
    };
    window.addEventListener("article-deleted", onDeleted);
    return () => window.removeEventListener("article-deleted", onDeleted);
  }, []);

  useEffect(() => {
    fetch("/api/categories")
      .then((r) => (r.ok ? r.json() : []))
      .then((cats: CategoryOption[]) => setCategories(cats.filter((c) => c.slug !== "weather")))
      .catch(() => {});
    fetch("/api/search-links")
      .then((r) => (r.ok ? r.json() : { links: [] }))
      .then((data) => setLinks(data.links ?? []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!query) {
      setArticles([]);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    const qs = new URLSearchParams({ q: query, limit: "100" });
    if (category) qs.set("category", category);
    if (from) qs.set("from", from);
    if (to) qs.set("to", to);
    if (saved) qs.set("saved", "true");

    fetch(`/api/articles/search?${qs}`)
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
  }, [query, category, from, to, saved]);

  // Web results are independent of the local filters (they can't apply to
  // a remote index), so they only re-run when the term changes.
  useEffect(() => {
    if (!query) {
      setRemote(null);
      return;
    }
    let cancelled = false;
    setRemote(null);
    fetch(`/api/search/remote?q=${encodeURIComponent(query)}`)
      .then((r) => (r.ok ? r.json() : { results: [], error: "Remote search is unavailable right now" }))
      .then((data) => { if (!cancelled) setRemote({ results: data.results ?? [], error: data.error ?? null }); })
      .catch(() => { if (!cancelled) setRemote({ results: [], error: "Remote search is unavailable right now" }); });
    return () => { cancelled = true; };
  }, [query]);

  function setFilter(key: (typeof FILTER_KEYS)[number], value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  }

  const hasFilters = FILTER_KEYS.some((k) => params.get(k));
  const categoryName = categories.find((c) => c.slug === category)?.name ?? category;

  return (
    <div className="page">
      <div className="page-title">Search</div>
      <div className="page-sub">
        {query
          ? loading
            ? `Searching for "${query}"…`
            : `${articles.length} result${articles.length === 1 ? "" : "s"} for "${query}"${category ? ` in ${categoryName}` : ""}`
          : "Type a search term above"}
      </div>

      <div className="search-filters">
        <select
          className="feed-select"
          value={category}
          onChange={(e) => setFilter("category", e.target.value)}
          aria-label="Category filter"
        >
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c.slug} value={c.slug}>{c.name}</option>
          ))}
        </select>
        <label>
          From <input type="date" className="feed-select" value={from} max={to || undefined}
            onChange={(e) => setFilter("from", e.target.value)} aria-label="From date" />
        </label>
        <label>
          To <input type="date" className="feed-select" value={to} min={from || undefined}
            onChange={(e) => setFilter("to", e.target.value)} aria-label="To date" />
        </label>
        <label>
          <input type="checkbox" checked={saved} onChange={(e) => setFilter("saved", e.target.checked ? "1" : "")} />
          Saved only
        </label>
        {hasFilters && (
          <button
            className="tb-btn"
            onClick={() => setParams(query ? { q: query } : {}, { replace: true })}
          >
            Clear filters
          </button>
        )}
      </div>

      {query && links.length > 0 && (
        <div className="search-links">
          <span className="search-links-label">Search elsewhere:</span>
          {links.map((l) => (
            <a
              key={l.name}
              className="search-link-chip"
              href={l.template.replace("{q}", encodeURIComponent(query))}
              target="_blank"
              rel="noopener noreferrer"
            >
              {l.name} ↗
            </a>
          ))}
          <Link to="/settings" className="search-links-edit" title="Edit search links in Settings">edit</Link>
        </div>
      )}

      {error && <div className="ask-error">{error}</div>}

      {!loading && query && articles.length === 0 && !error && (
        <EmptyState
          title="No matches in your library"
          description={`Nothing found for "${query}"${hasFilters ? " with these filters" : ""}. Search covers article titles, summaries, and full text.`}
        />
      )}

      {/* autoMarkRead off: scrolling a result list is not reading the
          articles, and silently marking them read would lose them from the
          unread views. */}
      {articles.length > 0 && (
        <ArticleList articles={articles} viewMode="list" autoMarkRead={false} />
      )}

      {query && (
        <div className="remote-results">
          <div className="group-label">From the web · Hacker News</div>
          {remote === null ? (
            <div className="ask-loading">Searching…</div>
          ) : remote.error ? (
            <div className="ask-notice">{remote.error}. Your library results above are unaffected.</div>
          ) : remote.results.length === 0 ? (
            <div className="ask-notice">No Hacker News stories match.</div>
          ) : (
            <ul className="article-list">
              {remote.results.map((r) => (
                <li key={r.discussionUrl ?? r.url} className="article-item">
                  <span className="article-dot" />
                  <div className="article-body">
                    <a href={r.url} target="_blank" rel="noopener noreferrer" className="article-title">
                      {r.title}
                    </a>
                    <div className="article-meta">
                      {[
                        r.points != null ? `${r.points} points` : null,
                        r.comments != null ? `${r.comments} comments` : null,
                      ].filter(Boolean).join(" · ")}
                      {r.discussionUrl && r.discussionUrl !== r.url && (
                        <>
                          {" · "}
                          <a href={r.discussionUrl} target="_blank" rel="noopener noreferrer">discussion</a>
                        </>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
