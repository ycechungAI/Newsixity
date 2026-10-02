"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { Link } from "react-router";
import type { Article } from "@/types";
import { timeAgo } from "@/lib/utils/date";
import { truncate, stripHtml } from "@/lib/utils/sanitize";
import { isVideoUrl } from "@/lib/utils/video";
import { parseHttpUrl } from "@/lib/utils/url";
import { enqueueMarkRead } from "@/lib/articles/markReadQueue";
import VideoEmbed from "./VideoEmbed";
import Highlight from "@/components/ui/Highlight";
import { confirmDialog, notify } from "@/lib/ui/dialog";

interface ArticleCardProps {
  article: Article | undefined;
  autoMarkRead?: boolean;
  cardView?: boolean;
}

function extractPreview(article: Article): string | null {
  if (article.summary) return truncate(article.summary, 220);
  if (!article.content) return null;
  const m = article.content.match(/<p[^>]*>([\s\S]*?)<\/p>/i);
  if (m) {
    const t = stripHtml(m[1]).trim();
    if (t.length > 30) return truncate(t, 220);
  }
  const plain = stripHtml(article.content).trim();
  return plain.length > 30 ? truncate(plain, 220) : null;
}

export default function ArticleCard({ article, autoMarkRead = true, cardView = false }: ArticleCardProps) {
  const articleId = article?.id ?? null;
  const [isRead, setIsRead]   = useState(article?.isRead ?? false);
  const [isSaved, setIsSaved] = useState(article?.isSaved ?? false);
  const [isDeleted, setIsDeleted] = useState(false);
  const cardRef   = useRef<HTMLElement | null>(null);
  const markedRef = useRef(false);

  // Auto-mark read when scrolled into view (1 s)
  useEffect(() => {
    if (!articleId || isRead || markedRef.current || !autoMarkRead) return;
    const el = cardRef.current;
    if (!el) return;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const obs = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        timer = setTimeout(() => {
          if (markedRef.current) return;
          markedRef.current = true;
          enqueueMarkRead(articleId).then((categorySlug) => {
            setIsRead(true);
            window.dispatchEvent(new CustomEvent("article-read", {
              detail: { articleId, categorySlug },
            }));
          });
          obs.disconnect();
        }, 1000);
      } else {
        if (timer) { clearTimeout(timer); timer = null; }
      }
    }, { threshold: 0.5 });
    obs.observe(el);
    return () => { if (timer) clearTimeout(timer); obs.disconnect() };
  }, [articleId, isRead, autoMarkRead]);

  const toggleRead = useCallback(async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!articleId) return;
    const next = !isRead;
    try {
      const res = await fetch(`/api/articles/${articleId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_read: next }),
      });
      if (res.ok) {
        const data = await res.json();
        setIsRead(next);
        markedRef.current = next;
        window.dispatchEvent(new CustomEvent(next ? "article-read" : "article-unread", {
          detail: { articleId, categorySlug: data.categorySlug },
        }));
      }
    } catch { /* silent */ }
  }, [articleId, isRead]);

  const toggleSave = useCallback(async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!articleId) return;
    try {
      const res = await fetch(`/api/articles/${articleId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_saved: !isSaved }),
      });
      if (res.ok) setIsSaved(s => !s);
    } catch { /* silent */ }
  }, [articleId, isSaved]);

  const handleDelete = useCallback(async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!articleId) return;
    
    if (await confirmDialog("Are you sure you want to completely delete this article?")) {
      try {
        const res = await fetch(`/api/articles/${articleId}`, {
          method: "DELETE",
        });
        if (res.ok) {
          setIsDeleted(true);
          // Tell every other mounted view, so the article also disappears
          // from the sidebar counts and any other list showing it. Hiding
          // only this card left the same article visible elsewhere until a
          // manual refetch, which reads as "delete did nothing".
          window.dispatchEvent(
            new CustomEvent("article-deleted", { detail: { id: articleId } })
          );
        } else {
          // Never fail silently: an unreachable or rejected delete used to
          // be indistinguishable from a successful one, so the only symptom
          // was a button that appeared to do nothing.
          const data = await res.json().catch(() => ({}));
          void notify(`Could not delete this article: ${data.error ?? data.detail ?? res.status}`);
        }
      } catch {
        void notify("Could not delete this article — the app could not reach the server.");
      }
    }
  }, [articleId]);

  if (!article || isDeleted) return null;

  // Card view (grid layout with optional image or video embed)
  if (cardView) {
    const preview = extractPreview(article);
    const meta = [article.feedName, timeAgo(article.publishedAt)].filter(Boolean).join(" · ");
    const safeOriginalUrl = parseHttpUrl(article.link)?.toString() ?? article.link;
    const isVideo = isVideoUrl(safeOriginalUrl);
    return (
      <div ref={(node) => { cardRef.current = node; }} className={`article-card${isRead ? " is-read" : ""}`}>
        {isVideo ? (
          <VideoEmbed url={safeOriginalUrl} title={article.title} />
        ) : article.imageUrl ? (
          <img
            src={article.imageUrl}
            alt=""
            className="card-img"
            loading="lazy"
            onError={e => { (e.target as HTMLImageElement).style.display = "none" }}
          />
        ) : null}
        <div className="card-body">
          <Link to={`/article/${article.id}`} className="card-title">{article.title}</Link>
          <div className="card-meta">{meta}</div>
          {article.highlight ? (
            <div className="card-preview"><Highlight snippet={article.highlight} /></div>
          ) : (
            preview && <div className="card-preview">{preview}</div>
          )}
          <div className="card-actions">
            <button className={`act-btn${isSaved ? " is-saved" : ""}`} onClick={toggleSave} title={isSaved ? "Unsave" : "Save"}>{isSaved ? "★" : "☆"}</button>
            <button className="act-btn" onClick={toggleRead} title={isRead ? "Mark unread" : "Mark read"}>{isRead ? "○" : "●"}</button>
            <a className="act-btn" href={safeOriginalUrl} target="_blank" rel="noopener noreferrer" title="Open original">↗</a>
            <button className="act-btn" onClick={handleDelete} title="Delete article" style={{ color: "var(--subtle)" }}>×</button>
          </div>
        </div>
      </div>
    );
  }

  const preview = extractPreview(article);

  const meta = [
    article.feedName,
    timeAgo(article.publishedAt),
    article.categorySlug
      ? article.categorySlug.replace(/-/g, " ")
      : null,
    article.summary ? "✦ AI" : null,
    article.isPromoted ? "★ top" : null,
  ].filter(Boolean).join(" · ");

  return (
    <li ref={(node) => { cardRef.current = node; }} className={`article-item${isRead ? " is-read" : ""}`}>
      <span className="article-dot" />
      <div className="article-body">
        <Link to={`/article/${article.id}`} className="article-title">
          {article.title}
        </Link>
        <div className="article-meta">{meta}</div>
        {article.highlight ? (
          <div className="article-preview"><Highlight snippet={article.highlight} /></div>
        ) : (
          preview && <div className="article-preview">{preview}</div>
        )}
      </div>
      <div className="article-actions">
        <button className={`act-btn${isSaved ? " is-saved" : ""}`} onClick={toggleSave} title={isSaved ? "Unsave" : "Save"}>
          {isSaved ? "★" : "☆"}
        </button>
        <button className="act-btn" onClick={toggleRead} title={isRead ? "Mark unread" : "Mark read"}>
          {isRead ? "○" : "●"}
        </button>
        <a
          className="act-btn"
          href={article.link}
          target="_blank"
          rel="noopener noreferrer"
          title="Open original"
        >
          ↗
        </a>
        <button className="act-btn" onClick={handleDelete} title="Delete article" style={{ color: "var(--subtle)", marginLeft: "auto" }}>
          ×
        </button>
      </div>
    </li>
  );
}
