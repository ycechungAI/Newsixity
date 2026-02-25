import Link from "next/link";
import { notFound } from "next/navigation";
import { getArticleById, markArticleRead, getArticleGroupsByCategory } from "@/lib/db/queries";
import { formatDate } from "@/lib/utils/date";
import { isVideoUrl, extractVideoInfo, fetchYouTubePlaylist, type PlaylistItem, type PlaylistPagination } from "@/lib/utils/video";
import { isSearchEngineUrl, detectSearchEngine } from "@/lib/utils/search";
import { extractSearchResults } from "@/lib/server/search-extractor";
import { parseHttpUrl } from "@/lib/utils/url";
import ArticleSummary from "@/components/articles/ArticleSummary";
import VideoEmbed from "@/components/articles/VideoEmbed";
import WebPageEmbed from "@/components/articles/WebPageEmbed";
import SearchResultsSummary from "@/components/articles/SearchResultsSummary";

export default async function ArticlePage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ page?: string }>;
}) {
  const { id } = await params;
  const { page: pageParam } = await searchParams;
  const articleId = parseInt(id, 10);
  const currentPage = pageParam ? parseInt(pageParam, 10) : 1;

  if (isNaN(articleId)) notFound();

  const article = getArticleById(articleId);

  if (!article) {
    return (
      <div className="page">
        <Link href="/" className="article-back">← Back to feed</Link>
        <div className="empty">
          <div className="empty-title">Article not found</div>
          <div className="empty-desc">This article may have been removed or the link is invalid.</div>
        </div>
      </div>
    );
  }

  markArticleRead(articleId);
  const safeArticleLink = parseHttpUrl(article.link)?.toString() ?? null;

  let searchResults = null;
  let searchQuery: string | undefined;

  if (article.feedName === "Manual Links" && safeArticleLink && isSearchEngineUrl(safeArticleLink)) {
    try {
      const results = await extractSearchResults(safeArticleLink);
      if (results.length > 0) {
        searchResults = results.map(r => ({ title: r.title, link: r.url }));
        const info = detectSearchEngine(safeArticleLink);
        searchQuery = info?.query || undefined;
      }
    } catch { /* silent */ }
  }

  let playlistItems: PlaylistItem[] = [];
  let playlistPagination: PlaylistPagination = { currentPage: 1, pageSize: 10, totalItems: 0, totalPages: 0 };

  if (article.feedName === "Manual Links" && safeArticleLink && isVideoUrl(safeArticleLink)) {
    const videoInfo = extractVideoInfo(safeArticleLink);
    if (videoInfo?.playlistId) {
      try {
        const result = await fetchYouTubePlaylist(videoInfo.playlistId, { page: currentPage, pageSize: 10 });
        playlistItems = result.items;
        playlistPagination = result.pagination;
      } catch { /* silent */ }
    }
  }

  let relatedArticles = null;
  if (article.groupId && article.categorySlug) {
    const groups = getArticleGroupsByCategory(article.categorySlug, { limit: 50, promotedOnly: false });
    const match = groups.find(g => g.id === article.groupId);
    if (match) relatedArticles = match.articles.filter(a => a.id !== article.id);
  }

  const meta = [
    article.feedName,
    article.author,
    formatDate(article.publishedAt),
  ].filter(Boolean).join(" · ");

  return (
    <div className="article-page page">
      <Link href="/" className="article-back">← Back to feed</Link>

      <article>
        <div className="article-detail-meta">{meta}</div>
        <h1 className="article-detail-title">{article.title}</h1>

        {article.feedName === "Manual Links" && safeArticleLink && (
          <>
            {isVideoUrl(safeArticleLink) ? (
              <VideoEmbed
                url={safeArticleLink}
                title={article.title}
                playlistItems={playlistItems}
                playlistPagination={playlistPagination}
              />
            ) : !isSearchEngineUrl(safeArticleLink) ? (
              <WebPageEmbed url={safeArticleLink} title={article.title} />
            ) : null}
          </>
        )}

        {((searchResults && searchResults.length > 0) || (article.feedName === "Manual Links" && safeArticleLink && isSearchEngineUrl(safeArticleLink))) && (
          <SearchResultsSummary
            results={searchResults || []}
            query={searchQuery}
            fallbackLink={article.feedName === "Manual Links" && safeArticleLink && isSearchEngineUrl(safeArticleLink) ? safeArticleLink : undefined}
          />
        )}

        <ArticleSummary articleId={article.id} initialSummary={article.summary} />

        {article.content && (
          <div className="prose">{article.content}</div>
        )}

        {safeArticleLink && (
          <a href={safeArticleLink} target="_blank" rel="noopener noreferrer" className="article-open-btn">
            ↗ Read Original Article
          </a>
        )}

        {relatedArticles && relatedArticles.length > 0 && (
          <div style={{ marginTop: 20, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
            <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>Related Coverage</div>
            <ul className="related-list">
              {relatedArticles.map(r => (
                <li key={r.id} className="related-item">
                  <Link href={`/article/${r.id}`} className="related-title">{r.title}</Link>
                  <div className="related-meta">
                    {r.feedName}{r.publishedAt && ` · ${formatDate(r.publishedAt)}`}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </article>
    </div>
  );
}
