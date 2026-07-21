"use client";

import { useEffect, useState } from "react";
import type { Article, Category } from "@/types";
import ArticleList from "@/components/articles/ArticleList";
import type { ViewMode } from "@/components/articles/ArticleList";
import SavedViewModeToggle from "@/components/ui/SavedViewModeToggle";
import Pagination from "@/components/ui/Pagination";
import EmptyState from "@/components/ui/EmptyState";
import CategoryTabs from "@/components/ui/CategoryTabs";

type SavedViewMode = "cards" | "compact" | "list" | "categories" | "sources" | "timeline";

function getPerPage(viewMode: SavedViewMode) {
  if (viewMode === "list") return 200;
  if (viewMode === "compact") return 50;
  return 30;
}

function toArticleListViewMode(mode: SavedViewMode): ViewMode {
  if (mode === "cards") return "topics";
  return mode;
}

export default function SavedPage() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [viewMode, setViewMode] = useState<SavedViewMode>("cards");
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const perPage = getPerPage(viewMode);

  useEffect(() => {
    Promise.all([
      fetch("/api/categories").then(r => r.json()),
      fetch("/api/articles?limit=1000").then(r => r.json()),
    ])
      .then(([cats, arts]: [Category[], Article[]]) => {
        setCategories(cats || []);
        setArticles((arts || []).filter((a: Article) => a.isSaved));
      });
  }, []);

  const filtered = selectedCategory
    ? articles.filter((a: Article) => a.categorySlug === selectedCategory)
    : articles;

  const totalPages = Math.max(1, Math.ceil(filtered.length / perPage));
  const paginatedArticles = filtered.slice(
    (currentPage - 1) * perPage,
    currentPage * perPage
  );

  const categoryName = selectedCategory
    ? categories.find((c: Category) => c.slug === selectedCategory)?.name
    : null;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="page-title">Saved</div>
          <div className="page-sub">
            {filtered.length} bookmarked article{filtered.length !== 1 ? "s" : ""}
            {categoryName && ` in ${categoryName}`}
          </div>
        </div>
        <SavedViewModeToggle viewMode={viewMode} onChange={setViewMode} />
      </div>

      <CategoryTabs
        categories={categories}
        activeSlug={selectedCategory}
        onSelectCategory={setSelectedCategory}
      />

      {paginatedArticles.length > 0 ? (
        <>
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            onChange={setCurrentPage}
          />
          <ArticleList
            articles={paginatedArticles}
            viewMode={toArticleListViewMode(viewMode)}
            emptyMessage="No saved articles"
          />
        </>
      ) : (
        <EmptyState
          title={selectedCategory ? `No saved ${selectedCategory} articles` : "No saved articles"}
          description={selectedCategory ? `No bookmarked articles in ${selectedCategory}.` : "Bookmark articles to find them here."}
        />
      )}
    </div>
  );
}
