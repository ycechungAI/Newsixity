import { getCategoryBySlug, getArticleGroupsByCategory, getArticlesByCategory, getArticleCountByCategory } from "@/lib/db/queries";
import ViewModeToggle from "@/components/ui/ViewModeToggle";
import ArticleListWithToolbar from "@/components/articles/ArticleListWithToolbar";
import Pagination from "@/components/ui/Pagination";
import EmptyState from "@/components/ui/EmptyState";
import { RefreshButton } from "@/components/ui/RefreshButton";
import AddLinkButton from "@/components/ui/AddLinkButton";
import { notFound, redirect } from "next/navigation";

type ViewMode = "topics" | "compact" | "sources" | "timeline" | "list";

function getPerPage(viewMode: ViewMode) {
  if (viewMode === "list") return 200;
  if (viewMode === "compact") return 50;
  return 30;
}

export default async function CategoryPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ view?: string; page?: string }>;
}) {
  const { slug } = await params;

  if (slug === "weather") {
    redirect("/weather");
  }

  const { view, page: pageParam } = await searchParams;
  const viewMode: ViewMode = (view === "compact" || view === "sources" || view === "timeline" || view === "list") ? view : "topics";
  const currentPage = Math.max(1, parseInt(pageParam ?? "1", 10) || 1);
  const perPage = getPerPage(viewMode);

  const category = getCategoryBySlug(slug);
  if (!category) {
    notFound();
  }

  const counts = getArticleCountByCategory();
  const categoryCount = counts.find((c) => c.slug === slug);
  const categoryUnread = categoryCount?.unread ?? 0;
  const categoryTotal = categoryCount?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(categoryTotal / perPage));

  // Only fetch groups on page 1 in topics view
  let groups = null;
  if (viewMode === "topics" && currentPage === 1) {
    groups = getArticleGroupsByCategory(slug, perPage);
  }

  // Fetch flat articles for other views, or as fallback
  let articles = null;
  if (viewMode !== "topics" || !groups || groups.length === 0) {
    articles = getArticlesByCategory(slug, {
      limit: perPage,
      offset: (currentPage - 1) * perPage,
    });
  }

  const hasContent = (articles && articles.length > 0) || (groups && groups.length > 0);

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{category.name}</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Latest articles in {category.name}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {slug === "others" && <AddLinkButton />}
          <RefreshButton />
        </div>
      </div>

      <div className="mb-4 flex items-center justify-end">
        <ViewModeToggle viewMode={viewMode} />
      </div>

      {hasContent ? (
        <>
          <Pagination currentPage={currentPage} totalPages={totalPages} />
          <ArticleListWithToolbar
            articles={articles ?? undefined}
            groups={groups && groups.length > 0 ? groups : undefined}
            viewMode={viewMode}
            categorySlug={slug}
            unreadCount={categoryUnread}
          />
        </>
      ) : (
        <EmptyState
          title={`No articles in ${category.name}`}
          description="Refresh your feeds to get the latest articles in this category."
          action={<RefreshButton />}
        />
      )}
    </div>
  );
}
