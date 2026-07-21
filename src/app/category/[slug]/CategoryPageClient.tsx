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

function getPerPage(viewMode: ViewMode) {
  if (viewMode === "list") return 200;
  if (viewMode === "compact") return 50;
  return 30;
}

export default function CategoryPageClient({ slug }: { slug: string }) {
  const router = useRouter();
  const [articles, setArticles] = useState<Article[]>([]);
  const [category, setCategory] = useState<Category | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("topics");
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

  useEffect(() => {
    if (slug === "weather" || slug === "finance") return;

    Promise.all([
      fetch("/api/categories").then((r) => r.json()),
      fetch(`/api/articles?category=${encodeURIComponent(slug)}&limit=1000`).then((r) =>
        r.json()
      ),
    ])
      .then(([cats, arts]: [Category[], Article[]]) => {
        setCategory((cats || []).find((c) => c.slug === slug) ?? null);
        setArticles(arts || []);
      })
      .finally(() => setLoading(false));
  }, [slug]);

  if (slug === "weather" || slug === "finance") return null;

  const totalPages = Math.max(1, Math.ceil(articles.length / perPage));
  const paginatedArticles = articles.slice(
    (currentPage - 1) * perPage,
    currentPage * perPage
  );
  const unreadCount = articles.filter((a) => !a.isRead).length;
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

      <ViewModeToggle viewMode={viewMode} onChange={setViewMode} />

      {!loading && articles.length === 0 ? (
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
            articles={paginatedArticles}
            viewMode={viewMode}
            categorySlug={slug}
            unreadCount={unreadCount}
          />
        </>
      )}
    </div>
  );
}
