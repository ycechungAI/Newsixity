import { getSavedArticles, getSavedArticleCount, getCategories } from "@/lib/db/queries";
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

export default async function SavedPage({
  searchParams,
}: {
  searchParams: Promise<{ view?: string; page?: string; category?: string }>;
}) {
  const { view, page: pageParam, category } = await searchParams;
  const viewMode: SavedViewMode =
    view === "compact" || view === "list" || view === "categories" || view === "sources" || view === "timeline"
      ? view
      : "cards";
  const currentPage = Math.max(1, parseInt(pageParam ?? "1", 10) || 1);
  const perPage = getPerPage(viewMode);

  const allCategories = getCategories().map((cat) => ({ ...cat, total: 0, unread: 0 }));
  const totalSaved = getSavedArticleCount(category);
  const totalPages = Math.max(1, Math.ceil(totalSaved / perPage));

  const articles = getSavedArticles({
    limit: perPage,
    offset: (currentPage - 1) * perPage,
    categorySlug: category,
  });

  const categoryName = category ? (allCategories.find((c) => c.slug === category)?.name ?? category) : null;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="page-title">Saved</div>
          <div className="page-sub">
            {totalSaved} bookmarked article{totalSaved !== 1 ? "s" : ""}
            {categoryName && ` in ${categoryName}`}
          </div>
        </div>
        <SavedViewModeToggle viewMode={viewMode} />
      </div>

      <CategoryTabs
        categories={allCategories}
        activeSlug={category}
        basePath="/saved"
        preserveParams={{ view }}
      />

      {articles.length > 0 ? (
        <>
          <Pagination currentPage={currentPage} totalPages={totalPages} searchParams={{ view, category }} />
          <ArticleList
            articles={articles}
            viewMode={toArticleListViewMode(viewMode)}
            emptyMessage="No saved articles"
          />
        </>
      ) : (
        <EmptyState
          title={category ? `No saved ${category} articles` : "No saved articles"}
          description={category ? `No bookmarked articles in ${category}.` : "Bookmark articles to find them here."}
        />
      )}
    </div>
  );
}
