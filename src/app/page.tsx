"use client";

import { useEffect, useState } from "react";
import type { Article } from "@/types";
import ViewModeToggle from "@/components/ui/ViewModeToggle";
import ArticleListWithToolbar from "@/components/articles/ArticleListWithToolbar";
import Pagination from "@/components/ui/Pagination";

type ViewMode = "topics" | "cards" | "compact" | "sources" | "timeline" | "list";

export default function HomePage() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>("topics");
  const [currentPage, setCurrentPage] = useState(1);

  const perPage = viewMode === "list" ? 200 : viewMode === "compact" ? 50 : 30;

  useEffect(() => {
    fetch("/api/articles?limit=1000")
      .then(r => r.json())
      .then((data: Article[]) => {
        setArticles(data || []);
      });
  }, []);

  const totalArticles = articles.length;
  const totalPages = Math.max(1, Math.ceil(totalArticles / perPage));
  const paginatedArticles = articles.slice(
    (currentPage - 1) * perPage,
    currentPage * perPage
  );

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="page-title">Discover</div>
          <div className="page-sub">Latest from all feeds</div>
        </div>
      </div>

      <ViewModeToggle viewMode={viewMode} onChange={setViewMode} />

      {articles.length > 0 ? (
        <>
          <Pagination currentPage={currentPage} totalPages={totalPages} onChange={setCurrentPage} />
          <ArticleListWithToolbar
            articles={paginatedArticles}
            viewMode={viewMode}
            unreadCount={articles.filter((a: Article) => !a.isRead).length}
          />
        </>
      ) : (
        <div className="empty">
          <div className="empty-title">No articles yet</div>
          <div className="empty-desc">Use ↺ Refresh in the top bar to fetch the latest news.</div>
        </div>
      )}
    </div>
  );
}
