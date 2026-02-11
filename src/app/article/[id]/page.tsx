import Link from "next/link";
import { notFound } from "next/navigation";
import { getArticleById, markArticleRead, getArticleGroupsByCategory } from "@/lib/db/queries";
import { formatDate } from "@/lib/utils/date";
import { isVideoUrl } from "@/lib/utils/video";
import { isSearchEngineUrl, detectSearchEngine } from "@/lib/utils/search";
import { extractSearchResults } from "@/lib/server/search-extractor";
import ArticleSummary from "@/components/articles/ArticleSummary";
import VideoEmbed from "@/components/articles/VideoEmbed";
import WebPageEmbed from "@/components/articles/WebPageEmbed";
import SearchResultsSummary from "@/components/articles/SearchResultsSummary";

export default async function ArticlePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const articleId = parseInt(id, 10);

  if (isNaN(articleId)) {
    notFound();
  }

  const article = getArticleById(articleId);

  if (!article) {
    return (
      <div className="p-6">
        <Link
          href="/"
          className="mb-4 inline-flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
        >
          <svg
            className="h-4 w-4"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M15.75 19.5 8.25 12l7.5-7.5"
            />
          </svg>
          Back to feed
        </Link>
        <div className="mt-8 text-center">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Article not found</h1>
          <p className="mt-2 text-gray-500 dark:text-gray-400">
            This article may have been removed or the link is invalid.
          </p>
        </div>
      </div>
    );
  }

  // Mark the article as read server-side
  markArticleRead(articleId);

  // Fetch search results on-demand if this is a search engine article
  let searchResults = null;
  let searchQuery = null;

  console.log("[Article Page] feedName:", article.feedName, "link:", article.link);
  console.log("[Article Page] isSearchEngineUrl:", isSearchEngineUrl(article.link));

  if (article.feedName === "Manual Links" && isSearchEngineUrl(article.link)) {
    try {
      console.log("[Article Page] Fetching search results for:", article.link);
      const results = await extractSearchResults(article.link);
      console.log("[Article Page] Got", results.length, "results");

      if (results.length > 0) {
        // Convert ExtractedSearchResult to match component props
        searchResults = results.map((r) => ({
          id: 0, // Placeholder since results aren't stored as articles
          title: r.title,
          link: r.url,
        }));
        // Extract query from URL for display
        const searchInfo = detectSearchEngine(article.link);
        searchQuery = searchInfo?.query || undefined;
        console.log("[Article Page] Set searchResults:", searchResults.length, "query:", searchQuery);
      }
    } catch (error) {
      console.error("[Article Page] Failed to fetch search results:", error);
      // Don't fail the page, just skip displaying results
    }
  }

  // Find related articles if this article belongs to a group
  let relatedArticles = null;
  if (article.groupId && article.categorySlug) {
    const groups = getArticleGroupsByCategory(article.categorySlug, 50);
    const matchingGroup = groups.find((g) => g.id === article.groupId);
    if (matchingGroup) {
      relatedArticles = matchingGroup.articles.filter((a) => a.id !== article.id);
    }
  }

  return (
    <div className="p-6">
      <Link
        href="/"
        className="mb-6 inline-flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
      >
        <svg
          className="h-4 w-4"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M15.75 19.5 8.25 12l7.5-7.5"
          />
        </svg>
        Back to feed
      </Link>

      <article className="mx-auto max-w-3xl">
        {/* Source and metadata */}
        <div className="mb-4 flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
          <span className="font-medium text-gray-700 dark:text-gray-300">{article.feedName}</span>
          {article.author && (
            <>
              <span>&middot;</span>
              <span>{article.author}</span>
            </>
          )}
          <span>&middot;</span>
          <span>{formatDate(article.publishedAt)}</span>
        </div>

        {/* Title */}
        <h1 className="mb-6 text-3xl font-bold text-gray-900 dark:text-gray-100">
          {article.title}
        </h1>

        {/* Embedded Media for Manual Articles */}
        {article.feedName === "Manual Links" && article.link && (
          <div className="mb-8">
            {isVideoUrl(article.link) ? (
              <VideoEmbed url={article.link} title={article.title} />
            ) : !isSearchEngineUrl(article.link) ? (
              <WebPageEmbed url={article.link} title={article.title} />
            ) : null}
          </div>
        )}

        {/* Search Results Summary */}
        {(searchResults && searchResults.length > 0) || (article.feedName === "Manual Links" && isSearchEngineUrl(article.link)) ? (
          <div className="mb-8">
            <SearchResultsSummary
              results={searchResults || []}
              query={searchQuery || undefined}
              fallbackLink={article.feedName === "Manual Links" && isSearchEngineUrl(article.link) ? article.link : undefined}
            />
          </div>
        ) : null}

        {/* AI Summary — triggers on-demand summarization if none exists */}
        <ArticleSummary articleId={article.id} initialSummary={article.summary} />

        {/* Article content */}
        {article.content && (
          <div
            className="prose prose-gray dark:prose-invert max-w-none"
            dangerouslySetInnerHTML={{ __html: article.content }}
          />
        )}

        {/* Read original */}
        {article.link && (
          <div className="mt-8 border-t border-gray-200 dark:border-gray-700 pt-6">
            <a
              href={article.link}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-lg bg-gray-900 dark:bg-gray-100 px-5 py-2.5 text-sm font-medium text-white dark:text-gray-900 transition-colors hover:bg-gray-800 dark:hover:bg-gray-200"
            >
              Read Original Article
              <svg
                className="h-4 w-4"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M13.5 6H5.25A2.25 2.25 0 0 0 3 8.25v10.5A2.25 2.25 0 0 0 5.25 21h10.5A2.25 2.25 0 0 0 18 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"
                />
              </svg>
            </a>
          </div>
        )}

        {/* Related articles from the same group */}
        {relatedArticles && relatedArticles.length > 0 && (
          <div className="mt-10 border-t border-gray-200 dark:border-gray-700 pt-6">
            <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-gray-100">
              Related Coverage
            </h2>
            <ul className="space-y-3">
              {relatedArticles.map((related) => (
                <li key={related.id}>
                  <Link
                    href={`/article/${related.id}`}
                    className="group block rounded-lg border border-gray-200 dark:border-gray-700 p-4 transition-colors hover:border-sky-300 dark:hover:border-sky-600 hover:bg-sky-50 dark:hover:bg-sky-900/20"
                  >
                    <p className="font-medium text-gray-900 dark:text-gray-100 group-hover:text-sky-700 dark:group-hover:text-sky-400">
                      {related.title}
                    </p>
                    <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                      {related.feedName}
                      {related.publishedAt && (
                        <> &middot; {formatDate(related.publishedAt)}</>
                      )}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
      </article>
    </div>
  );
}
