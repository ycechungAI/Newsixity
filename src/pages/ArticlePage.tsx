import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Article } from "@/types";
import { formatDate } from "@/lib/utils/date";
import { isVideoUrl, extractVideoInfo, fetchYouTubePlaylist, type PlaylistItem } from "@/lib/utils/video";
import { parseHttpUrl } from "@/lib/utils/url";
import ArticleSummary from "@/components/articles/ArticleSummary";
import VideoEmbed from "@/components/articles/VideoEmbed";
import WebPageEmbed from "@/components/articles/WebPageEmbed";

export default function ArticlePage() {
  const { id: idParam } = useParams<{ id: string }>();

  const [article, setArticle] = useState<Article | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loading, setLoading] = useState(true);
  const [playlistItems, setPlaylistItems] = useState<PlaylistItem[]>([]);

  const articleId = idParam ? parseInt(idParam, 10) : NaN;
  const invalidId = !idParam || isNaN(articleId);

  useEffect(() => {
    if (invalidId) return;

    let cancelled = false;
    setLoading(true);
    setNotFound(false);

    // Fetching also marks the article read server-side, matching the old
    // Node SSR page's markArticleRead(articleId) on load.
    fetch(`/api/articles/${articleId}`)
      .then((r) => {
        if (!r.ok) throw new Error("not found");
        return r.json();
      })
      .then((data: Article) => {
        if (cancelled) return;
        setArticle(data);
        window.dispatchEvent(
          new CustomEvent("article-read", {
            detail: { articleId: data.id, categorySlug: data.categorySlug },
          })
        );
      })
      .catch(() => { if (!cancelled) setNotFound(true); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [invalidId, articleId]);

  useEffect(() => {
    if (!article) return;
    const safeLink = parseHttpUrl(article.link)?.toString() ?? article.link;
    if (article.feedName !== "Manual Links" || !isVideoUrl(safeLink)) return;
    const videoInfo = extractVideoInfo(safeLink);
    if (!videoInfo?.playlistId) return;

    let cancelled = false;
    // One fetch returns the whole playlist; VideoEmbed pages it for display.
    fetchYouTubePlaylist(videoInfo.playlistId).then((result) => {
      if (cancelled) return;
      setPlaylistItems(result.items);
    });
    return () => { cancelled = true; };
  }, [article]);

  if (!invalidId && loading) {
    return (
      <div className="page">
        <Link to="/" className="article-back">← Back to feed</Link>
      </div>
    );
  }

  if (invalidId || notFound || !article) {
    return (
      <div className="page">
        <Link to="/" className="article-back">← Back to feed</Link>
        <div className="empty">
          <div className="empty-title">Article not found</div>
          <div className="empty-desc">This article may have been removed or the link is invalid.</div>
        </div>
      </div>
    );
  }

  const safeArticleLink = parseHttpUrl(article.link)?.toString() ?? article.link;
  const meta = [article.feedName, article.author, formatDate(article.publishedAt)]
    .filter(Boolean)
    .join(" · ");
  const isManualVideo = article.feedName === "Manual Links" && isVideoUrl(safeArticleLink);
  const isManualWebPage =
    article.feedName === "Manual Links" && !isManualVideo && parseHttpUrl(article.link) !== null;

  return (
    <div className="article-page page">
      <Link to="/" className="article-back">← Back to feed</Link>

      <article>
        <div className="article-detail-meta">{meta}</div>
        <h1 className="article-detail-title">{article.title}</h1>

        {isManualVideo && (
          <VideoEmbed
            url={safeArticleLink}
            title={article.title}
            playlistItems={playlistItems}
            shared
            slotKey={String(article.id)}
          />
        )}
        {isManualWebPage && <WebPageEmbed url={safeArticleLink} title={article.title} />}

        <ArticleSummary articleId={article.id} initialSummary={article.summary} />

        {article.content && <div className="prose">{article.content}</div>}

        {safeArticleLink && (
          <a
            href={safeArticleLink}
            target="_blank"
            rel="noopener noreferrer"
            className="article-open-btn"
          >
            ↗ Read Original Article
          </a>
        )}
      </article>
    </div>
  );
}
