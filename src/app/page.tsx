import { getArticleGroupsByCategory, getArticlesByCategory, getArticleCountByCategory, searchArticles } from "@/lib/db/queries";
import ViewModeToggle from "@/components/ui/ViewModeToggle";
import ArticleListWithToolbar from "@/components/articles/ArticleListWithToolbar";
import Pagination from "@/components/ui/Pagination";

type ViewMode = "topics" | "cards" | "compact" | "sources" | "timeline" | "list";

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
  const params = await searchParams;
  const { search, category, view, page: pageParam } = params;
  const viewMode: ViewMode = (["cards", "compact", "sources", "timeline", "list"].includes(view ?? ""))
    ? (view as ViewMode)
    : "topics";
  const currentPage = Math.max(1, parseInt(pageParam ?? "1", 10) || 1);
  const perPage = getPerPage(viewMode);

  const counts = getArticleCountByCategory();
  const filteredCounts = category ? counts.filter(c => c.slug === category) : counts;
  const totalUnread  = filteredCounts.reduce((s, c) => s + c.unread, 0);
  const totalArticles = filteredCounts.reduce((s, c) => s + c.total, 0);
  const totalPages = Math.max(1, Math.ceil(totalArticles / perPage));

  let articles = null;
  let groups   = null;

  if (search) {
    articles = searchArticles(search, { category, limit: 50 });
  } else {
    if (viewMode === "topics" && currentPage === 1) {
      groups = getArticleGroupsByCategory(category || null, { limit: perPage, promotedOnly: false });
    }
    if (viewMode !== "topics" || !groups || groups.length === 0) {
      articles = getArticlesByCategory(category || null, {
        limit: perPage,
        offset: (currentPage - 1) * perPage,
        promotedOnly: false,
      });
    }
  }

  const hasContent = (articles && articles.length > 0) || (groups && groups.length > 0);

  const title = search
    ? `Search: "${search}"`
    : category
    ? category.charAt(0).toUpperCase() + category.slice(1).replace(/-/g, " ")
    : "Discover";

  const sub = search
    ? `${articles?.length ?? 0} results`
    : category
    ? `${category} articles`
    : "Latest from all feeds";

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="page-title">{title}</div>
          <div className="page-sub">{sub}</div>
        </div>
      </div>

      {!search && (
        <ViewModeToggle viewMode={viewMode} searchParams={params} />
      )}

      {hasContent ? (
        <>
          {!search && (
            <Pagination currentPage={currentPage} totalPages={totalPages} searchParams={params} />
          )}
          <ArticleListWithToolbar
            articles={articles ?? undefined}
            groups={groups && groups.length > 0 ? groups : undefined}
            viewMode={viewMode}
            unreadCount={totalUnread}
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
