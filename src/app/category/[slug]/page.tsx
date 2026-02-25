import { getCategoryBySlug, getArticleGroupsByCategory, getArticlesByCategory, getArticleCountByCategory } from "@/lib/db/queries";
import ViewModeToggle from "@/components/ui/ViewModeToggle";
import ArticleListWithToolbar from "@/components/articles/ArticleListWithToolbar";
import Pagination from "@/components/ui/Pagination";
import EmptyState from "@/components/ui/EmptyState";
import { RefreshButton } from "@/components/ui/RefreshButton";
import AddLinkButton from "@/components/ui/AddLinkButton";
import { notFound, redirect } from "next/navigation";

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

export default async function CategoryPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ view?: string; page?: string }>;
}) {
  const { slug } = await params;

  if (slug === "weather") redirect("/weather");
  if (slug === "finance") redirect("/finance");

  const { view, page: pageParam } = await searchParams;
  const defaultView = getDefaultView(slug);
  const validViews: ViewMode[] = ["topics", "cards", "compact", "sources", "timeline", "list"];
  const viewMode: ViewMode = validViews.includes(view as ViewMode) ? (view as ViewMode) : defaultView;
  const currentPage = Math.max(1, parseInt(pageParam ?? "1", 10) || 1);
  const perPage = getPerPage(viewMode);

  const category = getCategoryBySlug(slug);
  if (!category) notFound();

  const counts = getArticleCountByCategory();
  const categoryCount = counts.find((c) => c.slug === slug);
  const categoryUnread = categoryCount?.unread ?? 0;
  const categoryTotal = categoryCount?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(categoryTotal / perPage));

  let groups = null;
  if (viewMode === "topics" && currentPage === 1) {
    groups = getArticleGroupsByCategory(slug, { limit: perPage, promotedOnly: false });
  }

  let articles = null;
  if (viewMode !== "topics" || !groups || groups.length === 0) {
    articles = getArticlesByCategory(slug, {
      limit: perPage,
      offset: (currentPage - 1) * perPage,
      promotedOnly: false,
    });
  }

  const hasContent = (articles && articles.length > 0) || (groups && groups.length > 0);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="page-title">{category.name}</div>
          <div className="page-sub">Latest in {category.name}</div>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {slug === "others" && <AddLinkButton />}
          <RefreshButton />
        </div>
      </div>

      <ViewModeToggle viewMode={viewMode} searchParams={{ view }} />

      {hasContent ? (
        <>
          <Pagination currentPage={currentPage} totalPages={totalPages} searchParams={{ view }} />
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
