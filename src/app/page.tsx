import { getArticleGroupsByCategory, getArticlesByCategory, getArticleCountByCategory, searchArticles } from "@/lib/db/queries";
import ViewModeToggle from "@/components/ui/ViewModeToggle";
import ArticleListWithToolbar from "@/components/articles/ArticleListWithToolbar";
import Pagination from "@/components/ui/Pagination";
import EmptyState from "@/components/ui/EmptyState";
import { RefreshButton } from "@/components/ui/RefreshButton";

type ViewMode = "topics" | "compact" | "sources" | "timeline" | "list";

function getPerPage(viewMode: ViewMode) {
  if (viewMode === "list") return 200;
  if (viewMode === "compact") return 50;
  return 30;
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ search?: string; category?: string; view?: string; page?: string }>;
}) {
  const { search, category, view, page: pageParam } = await searchParams;
  const viewMode: ViewMode = (view === "compact" || view === "sources" || view === "timeline" || view === "list") ? view : "topics";
  const currentPage = Math.max(1, parseInt(pageParam ?? "1", 10) || 1);
  const perPage = getPerPage(viewMode);
  const counts = getArticleCountByCategory();

  // Filter counts if category is selected
  const filteredCounts = category ? counts.filter(c => c.slug === category) : counts;
  const totalUnread = filteredCounts.reduce((sum, c) => sum + c.unread, 0);
  const totalArticles = filteredCounts.reduce((sum, c) => sum + c.total, 0);
  const totalPages = Math.max(1, Math.ceil(totalArticles / perPage));

  let articles = null;
  let groups = null;

  if (search) {
    articles = searchArticles(search, { category, limit: 50 });
  } else {
    if (viewMode === "topics" && currentPage === 1) {
      groups = getArticleGroupsByCategory(category || null, perPage);
    }

    if (viewMode !== "topics" || !groups || groups.length === 0) {
      articles = getArticlesByCategory(category || null, {
        limit: perPage,
        offset: (currentPage - 1) * perPage,
      });
    }
  }

  const hasContent = (articles && articles.length > 0) || (groups && groups.length > 0);

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {search ? `Search: "${search}"` : "Discover"}
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {search
              ? `Showing results for "${search}"`
              : category
              ? `Showing ${category.charAt(0).toUpperCase() + category.slice(1).replace(/-/g, " ")} articles`
              : "Latest news from all your feeds"}
          </p>
        </div>
        <RefreshButton />
      </div>

      {!search && (
        <div className="mb-4 flex items-center justify-end">
          <ViewModeToggle viewMode={viewMode} />
        </div>
      )}

      {hasContent ? (
        <>
          {!search && <Pagination currentPage={currentPage} totalPages={totalPages} />}
          <ArticleListWithToolbar
            articles={articles ?? undefined}
            groups={groups && groups.length > 0 ? groups : undefined}
            viewMode={viewMode}
            unreadCount={totalUnread}
          />
        </>
      ) : (
        <EmptyState
          title="No articles yet"
          description="Refresh your feeds to start reading the latest news."
          action={<RefreshButton />}
        />
      )}
    </div>
  );
}
