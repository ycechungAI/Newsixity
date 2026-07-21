"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
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

export default function CategoryPageClient({ slug }: { slug: string }) {
  const router = useRouter();
  const [articles, setArticles] = useState<Article[]>([]);
  const [category, setCategory] = useState<CategoryWithCounts | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>(() => getDefaultView(slug));
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const perPage = getPerPage(viewMode);

  useEffect(() => {
    if (slug === "weather") {
      router.replace("/weather");
      return;
    }
    if (slug === "finance") {
      router.replace("/finance");
      return;
    }
  }, [slug, router]);

  // Category metadata (name, real total/unread counts) — fetched once per
  // slug, independent of pagination, since /api/categories already has it.
  useEffect(() => {
    if (slug === "weather" || slug === "finance") return;
    fetch("/api/categories")
      .then((r) => r.json())
      .then((cats: CategoryWithCounts[]) => {
        setCategory((cats || []).find((c) => c.slug === slug) ?? null);
      });
  }, [slug]);

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
    if (slug === "weather" || slug === "finance") return;

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
  }, [slug, currentPage, perPage]);

  if (slug === "weather" || slug === "finance") return null;

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
