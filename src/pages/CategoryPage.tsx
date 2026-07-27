import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import type { Article, Category } from "@/types";
import ViewModeToggle from "@/components/ui/ViewModeToggle";
import ArticleListWithToolbar from "@/components/articles/ArticleListWithToolbar";
import Pagination from "@/components/ui/Pagination";
import EmptyState from "@/components/ui/EmptyState";
import { RefreshButton } from "@/components/ui/RefreshButton";
import AddLinkButton from "@/components/ui/AddLinkButton";

type ViewMode = "topics" | "cards" | "compact" | "sources" | "timeline" | "list";

function getDefaultView(slug: string): ViewMode {
  if (slug === "others") return "cards";
  return "topics";
}

function getPerPage(viewMode: ViewMode) {
  if (viewMode === "list") return 200;
  if (viewMode === "compact") return 50;
  return 30;
}

interface CategoryWithCounts extends Category {
  total: number;
  unread: number;
}

// The weather/finance redirect now lives at the router level (see
// src/main.tsx: /category/weather and /category/finance are matched before
// this :slug route), so this component only ever renders for real category
// slugs — no redirect-in-effect needed here anymore.
function CategoryPageInner({ slug }: { slug: string }) {
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

  const [category, setCategory] = useState<CategoryWithCounts | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>(() => getDefaultView(slug));
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [refreshTick, setRefreshTick] = useState(0);

  const perPage = getPerPage(viewMode);

  // Listen for the global feeds-refreshed event (dispatched by
  // RefreshButton/ReadToggleToolbar) and bump a tick to re-run both the
  // category-count effect and the article-fetch effect below.
  useEffect(() => {
    const handleFeedsRefreshed = () => setRefreshTick((t) => t + 1);
    window.addEventListener("feeds-refreshed", handleFeedsRefreshed);
    return () => window.removeEventListener("feeds-refreshed", handleFeedsRefreshed);
  }, []);

  // Category metadata (name, real total/unread counts) — fetched once per
  // slug, independent of pagination, since /api/categories already has it.
  useEffect(() => {
    fetch("/api/categories")
      .then((r) => r.json())
      .then((cats: CategoryWithCounts[]) => {
        setCategory((cats || []).find((c) => c.slug === slug) ?? null);
      });
  }, [slug, refreshTick]);

  function handleViewModeChange(mode: ViewMode) {
    setViewMode(mode);
    setCurrentPage(1);
  }

  // The actual page of articles — real server-side offset/limit, not a
  // client-side slice of some arbitrarily capped fetch. Previously this
  // fetched limit=1000 and paginated in the browser, which meant every
  // category with more than 1000 articles showed the same
  // ceil(1000/30) = 34 pages regardless of its real total.
  useEffect(() => {
    let cancelled = false;
    const offset = (currentPage - 1) * perPage;
    fetch(`/api/articles?category=${encodeURIComponent(slug)}&limit=${perPage}&offset=${offset}`)
      .then((r) => r.json())
      .then((arts: Article[]) => {
        if (cancelled) return;
        setArticles(arts || []);
      })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [slug, currentPage, perPage, refreshTick]);

  const totalPages = Math.max(1, Math.ceil((category?.total ?? 0) / perPage));
  const unreadCount = category?.unread ?? 0;
  const categoryName = category?.name ?? slug;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="page-title">{categoryName}</div>
          <div className="page-sub">Latest in {categoryName}</div>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {slug === "others" && <AddLinkButton />}
          <RefreshButton />
        </div>
      </div>

      <ViewModeToggle viewMode={viewMode} onChange={handleViewModeChange} />

      {!loading && (category?.total ?? 0) === 0 ? (
        <EmptyState
          title={`No articles in ${categoryName}`}
          description="Refresh your feeds to get the latest articles in this category."
          action={<RefreshButton />}
        />
      ) : (
        <>
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            onChange={setCurrentPage}
          />
          <ArticleListWithToolbar
            articles={articles}
            viewMode={viewMode}
            categorySlug={slug}
            unreadCount={unreadCount}
          />
        </>
      )}
    </div>
  );
}

export default function CategoryPage() {
  const { slug } = useParams<{ slug: string }>();
  if (!slug) return null;
  // key={slug} forces a full remount (fresh loading/currentPage/viewMode
  // state) when navigating between categories client-side — React Router
  // does not remount on param change alone, matching the old Next behavior.
  return <CategoryPageInner key={slug} slug={slug} />;
}
