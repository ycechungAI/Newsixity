import type { Metadata } from "next";
import ArticleListWithToolbar from "@/components/articles/ArticleListWithToolbar";
import { getArticlesByCategory, getArticleCountByCategory, getPromotedArticleCount } from "@/lib/db/queries";
import Pagination from "@/components/ui/Pagination";
import EmptyState from "@/components/ui/EmptyState";
import ViewModeToggle from "@/components/ui/ViewModeToggle";

export const metadata: Metadata = {
  title: "Finance News - Newsixity",
  description: "Latest financial news from MarketWatch, CNBC, Yahoo Finance, and more",
};

type ViewMode = "topics" | "compact" | "sources" | "timeline" | "list";

function getPerPage(viewMode: ViewMode) {
  if (viewMode === "list") return 200;
  if (viewMode === "compact") return 50;
  return 30;
}

export default async function FinanceNewsPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; view?: string }>;
}) {
  const { page: pageParam, view } = await searchParams;
  const viewMode: ViewMode = (view === "compact" || view === "sources" || view === "timeline" || view === "list") ? view : "topics";
  const currentPage = Math.max(1, parseInt(pageParam ?? "1", 10) || 1);
  const perPage = getPerPage(viewMode);

  // Get article count for promoted (top) finance only
  const counts = getArticleCountByCategory();
  const financeCount = counts.find(c => c.slug === 'finance');
  const financeUnread = financeCount?.unread ?? 0;
  const totalArticles = getPromotedArticleCount("finance");
  const totalPages = Math.max(1, Math.ceil(totalArticles / perPage));

  // Fetch finance articles: only top/priority (promoted) for the financial section
  const financeArticles = getArticlesByCategory("finance", {
    limit: perPage,
    offset: (currentPage - 1) * perPage,
    promotedOnly: true,
  });

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
        <ViewModeToggle viewMode={viewMode} />
      </div>

      {financeArticles.length > 0 ? (
        <>
          <Pagination currentPage={currentPage} totalPages={totalPages} />
          <ArticleListWithToolbar
            articles={financeArticles}
            viewMode={viewMode}
            categorySlug="finance"
            unreadCount={financeUnread}
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
