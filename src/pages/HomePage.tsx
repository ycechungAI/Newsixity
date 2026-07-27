import { useEffect, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import type { Article, Category } from "@/types";
import ViewModeToggle from "@/components/ui/ViewModeToggle";
import ArticleListWithToolbar from "@/components/articles/ArticleListWithToolbar";
import Pagination from "@/components/ui/Pagination";

type ViewMode = "topics" | "cards" | "compact" | "sources" | "timeline" | "list";

interface CategoryWithCounts extends Category {
  total: number;
  unread: number;
}

export default function HomePage() {
  // A search must always land on its own results page. The old top-bar form
  // submitted GET /?search=term, which nothing read — so the feed just
  // re-rendered with every article (24 pages of them) and looked like a
  // broken search. Forward that shape to /search so any stale bookmark,
  // cached page, or old client still ends up somewhere correct.
  const [searchParams] = useSearchParams();
  const legacySearch = searchParams.get("search")?.trim();

  const [articles, setArticles] = useState<Article[]>([]);
  const [totalArticles, setTotalArticles] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>("topics");
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [refreshTick, setRefreshTick] = useState(0);

  const perPage = viewMode === "list" ? 200 : viewMode === "compact" ? 50 : 30;

  // Listen for the global feeds-refreshed event (dispatched by
  // RefreshButton/ReadToggleToolbar) and bump a tick to re-run both fetches.
  useEffect(() => {
    const handleFeedsRefreshed = () => setRefreshTick((t) => t + 1);
    window.addEventListener("feeds-refreshed", handleFeedsRefreshed);
    return () => window.removeEventListener("feeds-refreshed", handleFeedsRefreshed);
  }, []);

  // Real totals across every category (sum of /api/categories), not the size
  // of some arbitrarily capped fetch — previously this page (and every
  // category page) fetched limit=1000 and paginated client-side, so any
  // category/view with over 1000 articles always showed the same
  // ceil(1000/30) = 34 pages regardless of its actual total.
  useEffect(() => {
    fetch("/api/categories")
      .then((r) => r.json())
      .then((cats: CategoryWithCounts[]) => {
        const list = cats || [];
        setTotalArticles(list.reduce((sum, c) => sum + c.total, 0));
        setUnreadCount(list.reduce((sum, c) => sum + c.unread, 0));
      });
  }, [refreshTick]);

  function handleViewModeChange(mode: ViewMode) {
    setViewMode(mode);
    setCurrentPage(1);
  }

  useEffect(() => {
    let cancelled = false;
    const offset = (currentPage - 1) * perPage;
    fetch(`/api/articles?limit=${perPage}&offset=${offset}`)
      .then((r) => r.json())
      .then((data: Article[]) => {
        if (cancelled) return;
        setArticles(data || []);
      })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [currentPage, perPage, refreshTick]);

  const totalPages = Math.max(1, Math.ceil(totalArticles / perPage));

  // Placed after every hook so hook order stays constant between renders.
  if (legacySearch) {
    return <Navigate to={`/search?q=${encodeURIComponent(legacySearch)}`} replace />;
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="page-title">Discover</div>
          <div className="page-sub">Latest from all feeds</div>
        </div>
      </div>

      <ViewModeToggle viewMode={viewMode} onChange={handleViewModeChange} />

      {!loading && totalArticles === 0 ? (
        <div className="empty">
          <div className="empty-title">No articles yet</div>
          <div className="empty-desc">Use ↺ Refresh in the top bar to fetch the latest news.</div>
        </div>
      ) : (
        <>
          <Pagination currentPage={currentPage} totalPages={totalPages} onChange={setCurrentPage} />
          <ArticleListWithToolbar
            articles={articles}
            viewMode={viewMode}
            unreadCount={unreadCount}
          />
        </>
      )}
    </div>
  );
}
