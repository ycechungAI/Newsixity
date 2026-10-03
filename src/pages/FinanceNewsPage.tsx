import { useEffect, useState } from "react";
import type { Article, Category } from "@/types";
import ArticleListWithToolbar from "@/components/articles/ArticleListWithToolbar";
import Pagination from "@/components/ui/Pagination";
import EmptyState from "@/components/ui/EmptyState";
import ViewModeToggle from "@/components/ui/ViewModeToggle";
import SortToggle, { type SortMode } from "@/components/ui/SortToggle";

type ViewMode = "topics" | "cards" | "compact" | "sources" | "timeline" | "list";

interface CategoryWithCounts extends Category {
  total: number;
  unread: number;
}

function getPerPage(viewMode: ViewMode) {
  if (viewMode === "list") return 200;
  if (viewMode === "compact") return 50;
  return 30;
}

export default function FinanceNewsPage() {
  const [articles, setArticles] = useState<Article[]>([]);

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

  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>("topics");
  const [sort, setSort] = useState<SortMode>("relevance");
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [refreshTick, setRefreshTick] = useState(0);

  const perPage = getPerPage(viewMode);

  // Listen for the global feeds-refreshed event.
  useEffect(() => {
    const handleFeedsRefreshed = () => setRefreshTick((t) => t + 1);
    window.addEventListener("feeds-refreshed", handleFeedsRefreshed);
    return () => window.removeEventListener("feeds-refreshed", handleFeedsRefreshed);
  }, []);

  // Real total/unread for the finance category, not the size of a capped
  // fetch — see the Home/CategoryPageClient pagination fix for why.
  useEffect(() => {
    fetch("/api/categories")
      .then((r) => r.json())
      .then((cats: CategoryWithCounts[]) => {
        const finance = (cats || []).find((c) => c.slug === "finance");
        setTotal(finance?.total ?? 0);
        setUnreadCount(finance?.unread ?? 0);
      });
  }, [refreshTick]);

  function handleViewModeChange(mode: ViewMode) {
    setViewMode(mode);
    setCurrentPage(1);
  }

  useEffect(() => {
    let cancelled = false;
    const offset = (currentPage - 1) * perPage;
    fetch(`/api/articles?category=finance&sort=${sort}&limit=${perPage}&offset=${offset}`)
      .then((r) => r.json())
      .then((data: Article[]) => {
        if (cancelled) return;
        setArticles(data || []);
      })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [currentPage, perPage, sort, refreshTick]);

  const totalPages = Math.max(1, Math.ceil(total / perPage));

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="page-title">Finance News</div>
          <div className="page-sub">Latest articles from MarketWatch, CNBC, Yahoo Finance, and more</div>
        </div>
      </div>

      <div className="toolbar-row">
        <ViewModeToggle viewMode={viewMode} onChange={handleViewModeChange} />
        <SortToggle value={sort} onChange={(next) => { setSort(next); setCurrentPage(1); }} />
      </div>

      {!loading && total === 0 ? (
        <EmptyState
          title="No finance articles yet"
          description="Refresh your feeds to fetch the latest financial news."
        />
      ) : (
        <>
          <Pagination currentPage={currentPage} totalPages={totalPages} onChange={setCurrentPage} />
          <ArticleListWithToolbar
            articles={articles}
            viewMode={viewMode}
            categorySlug="finance"
            unreadCount={unreadCount}
            emptyMessage="No finance articles yet"
          />
        </>
      )}
    </div>
  );
}
