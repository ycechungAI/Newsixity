import { useEffect, useState } from "react";
import type { Article, Category } from "@/types";
import ArticleListWithToolbar from "@/components/articles/ArticleListWithToolbar";
import Pagination from "@/components/ui/Pagination";
import EmptyState from "@/components/ui/EmptyState";
import ViewModeToggle from "@/components/ui/ViewModeToggle";

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
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>("topics");
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
    fetch(`/api/articles?category=finance&limit=${perPage}&offset=${offset}`)
      .then((r) => r.json())
      .then((data: Article[]) => {
        if (cancelled) return;
        setArticles(data || []);
      })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [currentPage, perPage, refreshTick]);

  const totalPages = Math.max(1, Math.ceil(total / perPage));

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Finance News
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Latest articles from MarketWatch, CNBC, Yahoo Finance, and more
        </p>
      </div>

      <div className="mb-4 flex items-center justify-end">
        <ViewModeToggle viewMode={viewMode} onChange={handleViewModeChange} />
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
