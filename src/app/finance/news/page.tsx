"use client";

import { useEffect, useState } from "react";
import type { Article } from "@/types";
import ArticleListWithToolbar from "@/components/articles/ArticleListWithToolbar";
import Pagination from "@/components/ui/Pagination";
import EmptyState from "@/components/ui/EmptyState";
import ViewModeToggle from "@/components/ui/ViewModeToggle";

type ViewMode = "topics" | "cards" | "compact" | "sources" | "timeline" | "list";

function getPerPage(viewMode: ViewMode) {
  if (viewMode === "list") return 200;
  if (viewMode === "compact") return 50;
  return 30;
}

export default function FinanceNewsPage() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>("topics");
  const [currentPage, setCurrentPage] = useState(1);

  const perPage = getPerPage(viewMode);

  useEffect(() => {
    fetch("/api/articles?limit=1000")
      .then(r => r.json())
      .then((data: Article[]) => {
        setArticles((data || []).filter((a: Article) => a.categorySlug === "finance"));
      });
  }, []);

  const totalPages = Math.max(1, Math.ceil(articles.length / perPage));
  const paginatedArticles = articles.slice(
    (currentPage - 1) * perPage,
    currentPage * perPage
  );

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
        <ViewModeToggle viewMode={viewMode} onChange={(mode) => setViewMode(mode)} />
      </div>

      {paginatedArticles.length > 0 ? (
        <>
          <Pagination currentPage={currentPage} totalPages={totalPages} onChange={setCurrentPage} />
          <ArticleListWithToolbar
            articles={paginatedArticles}
            viewMode={viewMode}
            categorySlug="finance"
            unreadCount={articles.filter((a: Article) => !a.isRead).length}
            emptyMessage="No finance articles yet"
          />
        </>
      ) : (
        <EmptyState
          title="No finance articles yet"
          description="Refresh your feeds to fetch the latest financial news."
        />
      )}
    </div>
  );
}
