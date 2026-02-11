"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import type { Article } from "@/types";
import { timeAgo } from "@/lib/utils/date";
import { truncate, stripHtml } from "@/lib/utils/sanitize";
import { isVideoUrl } from "@/lib/utils/video";
import Modal from "@/components/ui/Modal";
import DeepResearch from "@/components/articles/DeepResearch";
import VideoEmbed from "@/components/articles/VideoEmbed";

interface ArticleCardProps {
  article: Article;
  compact?: boolean;
  listView?: boolean;
  autoMarkRead?: boolean;
}

const BookmarkOutlineIcon = () => (
  <svg
    className="w-4 h-4"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <path d="M5 5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16l-7-3.5L5 21V5z" />
  </svg>
);

const BookmarkFilledIcon = () => (
  <svg
    className="w-4 h-4"
    fill="currentColor"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <path d="M5 5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16l-7-3.5L5 21V5z" />
  </svg>
);

const ExternalLinkIcon = () => (
  <svg
    className="w-4 h-4"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3" />
  </svg>
);

const SummarizedIcon = () => (
  <svg
    className="w-3.5 h-3.5"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={2.5}
  >
    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
  </svg>
);

const ResearchIcon = () => (
  <svg
    className="w-4 h-4"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607zM10.5 7.5v6m3-3h-6" />
  </svg>
);

const TrashIcon = () => (
  <svg
    className="w-4 h-4"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
  </svg>
);

/** Extract the first meaningful paragraph from HTML content */
function extractFirstParagraph(html: string): string | null {
  // Try to find the first <p> tag content
  const pMatch = html.match(/<p[^>]*>([\s\S]*?)<\/p>/i);
  if (pMatch) {
    const text = stripHtml(pMatch[1]).trim();
    if (text.length > 30) return text;
  }

  // Fallback: strip all HTML and take the first chunk
  const plainText = stripHtml(html).trim();
  if (plainText.length < 30) return null;

  // Find the first sentence or paragraph break
  const firstBreak = plainText.indexOf("\n");
  if (firstBreak > 30 && firstBreak < 500) {
    return plainText.slice(0, firstBreak).trim();
  }

  return plainText;
}

function ReadCheckbox({
  isRead,
  onToggle,
}: {
  isRead: boolean;
  onToggle: (e: React.MouseEvent) => void;
}) {
  return (
    <button
      onClick={onToggle}
      className="flex-shrink-0 group/check"
      title={isRead ? "Mark as unread" : "Mark as read"}
    >
      <span
        className={`block w-3.5 h-3.5 rounded-full border-2 transition-colors ${
          isRead
            ? "bg-gray-300 dark:bg-gray-600 border-gray-300 dark:border-gray-600"
            : "bg-sky-500 border-sky-500"
        } group-hover/check:border-sky-400`}
      />
    </button>
  );
}

export default function ArticleCard({
  article,
  compact,
  listView,
  autoMarkRead = true,
}: ArticleCardProps) {
  const [isSaved, setIsSaved] = useState(article.isSaved);
  const [saving, setSaving] = useState(false);
  const [isRead, setIsRead] = useState(article.isRead);
  const [toggling, setToggling] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const cardRef = useRef<HTMLElement>(null);
  const markedRef = useRef(false);
  const hasSummary = Boolean(article.summary);
  const [showResearch, setShowResearch] = useState(false);
  const isManualArticle = article.feedName === "Manual Links";
  const isVideoArticle = isManualArticle && isVideoUrl(article.link);

  // Auto-mark article as read when scrolled into view
  useEffect(() => {
    if (isRead || compact || listView || markedRef.current || !autoMarkRead)
      return;

    const el = cardRef.current;
    if (!el) return;

    let timer: ReturnType<typeof setTimeout> | null = null;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          timer = setTimeout(async () => {
            if (markedRef.current) return;
            markedRef.current = true;

            try {
              const res = await fetch(`/api/articles/${article.id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ is_read: true }),
              });
              if (res.ok) {
                const data = await res.json();
                setIsRead(true);
                window.dispatchEvent(
                  new CustomEvent("article-read", {
                    detail: {
                      articleId: article.id,
                      categorySlug: data.categorySlug,
                    },
                  })
                );
              }
            } catch {
              markedRef.current = false;
            }

            observer.disconnect();
          }, 1000);
        } else {
          if (timer) {
            clearTimeout(timer);
            timer = null;
          }
        }
      },
      { threshold: 0.5 }
    );

    observer.observe(el);

    return () => {
      if (timer) clearTimeout(timer);
      observer.disconnect();
    };
  }, [article.id, isRead, compact, listView, autoMarkRead]);

  const handleToggleRead = useCallback(
    async (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (toggling) return;

      const newRead = !isRead;
      setToggling(true);
      try {
        const res = await fetch(`/api/articles/${article.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_read: newRead }),
        });
        if (res.ok) {
          const data = await res.json();
          setIsRead(newRead);
          if (newRead) {
            markedRef.current = true;
          } else {
            markedRef.current = false;
          }
          window.dispatchEvent(
            new CustomEvent(newRead ? "article-read" : "article-unread", {
              detail: {
                articleId: article.id,
                categorySlug: data.categorySlug,
              },
            })
          );
        }
      } catch {
        // silently fail
      } finally {
        setToggling(false);
      }
    },
    [article.id, isRead, toggling]
  );

  const handleSave = useCallback(
    async (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (saving) return;

      setSaving(true);
      try {
        const res = await fetch(`/api/articles/${article.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_saved: !isSaved }),
        });
        if (res.ok) {
          setIsSaved(!isSaved);
        }
      } catch {
        // silently fail
      } finally {
        setSaving(false);
      }
    },
    [article.id, isSaved, saving]
  );

  const handleDelete = useCallback(
    async (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (deleting) return;

      setDeleting(true);
      try {
        const res = await fetch(`/api/articles/manual?id=${article.id}`, {
          method: "DELETE",
        });
        if (res.ok) {
          // Dispatch event to notify parent component to refresh
          window.dispatchEvent(
            new CustomEvent("manual-article-deleted", {
              detail: { articleId: article.id },
            })
          );
          // Reload page to refresh the articles list
          window.location.reload();
        }
      } catch {
        // silently fail
      } finally {
        setDeleting(false);
        setShowDeleteConfirm(false);
      }
    },
    [article.id, deleting]
  );

  // List view: single-row email inbox style
  if (listView) {
    return (
      <>
        <div
          className={`flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors border-b border-gray-100 dark:border-gray-800 group ${
            isRead ? "opacity-60" : ""
          }`}
        >
          <ReadCheckbox isRead={isRead} onToggle={handleToggleRead} />
          {hasSummary ? (
            <span className="flex-shrink-0 text-emerald-500 dark:text-emerald-400" title="AI summarized">
              <SummarizedIcon />
            </span>
          ) : (
            <span className="flex-shrink-0 w-3.5" />
          )}
          <span className="text-xs text-sky-600 dark:text-sky-400 whitespace-nowrap w-20 truncate font-medium">
            {article.categorySlug
              ? article.categorySlug.charAt(0).toUpperCase() + article.categorySlug.slice(1).replace(/-/g, " ")
              : ""}
          </span>
          <span className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap w-24 truncate">
            {article.feedName}
          </span>
          <Link
            href={`/article/${article.id}`}
            className={`flex-1 truncate text-sm transition-colors group-hover:text-sky-600 dark:group-hover:text-sky-400 ${
              isRead
                ? "text-gray-500 dark:text-gray-400"
                : "text-gray-900 dark:text-gray-100 font-medium"
            }`}
          >
            {article.title}
          </Link>
          <span className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">
            {timeAgo(article.publishedAt)}
          </span>
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setShowResearch(true);
            }}
            className="flex-shrink-0 p-1 rounded text-gray-300 dark:text-gray-600 hover:text-sky-500 dark:hover:text-sky-400 transition-colors"
            title="Deep Research"
          >
            <ResearchIcon />
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className={`flex-shrink-0 p-1 rounded transition-colors ${
              isSaved
                ? "text-sky-500"
                : "text-gray-300 dark:text-gray-600 hover:text-gray-500 dark:hover:text-gray-400"
            }`}
            title={isSaved ? "Unsave" : "Save"}
          >
            {isSaved ? <BookmarkFilledIcon /> : <BookmarkOutlineIcon />}
          </button>
          {isManualArticle && (
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setShowDeleteConfirm(true);
              }}
              disabled={deleting}
              className="flex-shrink-0 p-1 rounded text-gray-300 dark:text-gray-600 hover:text-red-500 dark:hover:text-red-400 transition-colors"
              title="Delete"
            >
              <TrashIcon />
            </button>
          )}
        </div>
        <Modal
          isOpen={showResearch}
          onClose={() => setShowResearch(false)}
          title="Deep Research"
        >
          <DeepResearch articleId={article.id} articleTitle={article.title} />
        </Modal>

        {isManualArticle &&
          createPortal(
            <Modal
              isOpen={showDeleteConfirm}
              onClose={() => setShowDeleteConfirm(false)}
              title="Delete Link"
            >
              <div className="space-y-4">
                <p className="text-gray-600 dark:text-gray-400">
                  Are you sure you want to delete this link? This action cannot be undone.
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={() => setShowDeleteConfirm(false)}
                    className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors font-medium"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleDelete}
                    disabled={deleting}
                    className="flex-1 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {deleting ? "Deleting..." : "Delete"}
                  </button>
                </div>
              </div>
            </Modal>,
            document.body
          )}
      </>
    );
  }

  // Compact layout: small tile without description
  if (compact) {
    return (
      <article
        ref={cardRef}
        className={`bg-white dark:bg-gray-900 rounded-lg border border-gray-100 dark:border-gray-800 hover:border-sky-300 dark:hover:border-sky-700 transition-all overflow-hidden group ${
          isRead ? "opacity-60" : ""
        }`}
      >
        {isVideoArticle && (
          <div className="p-2 pb-0">
            <VideoEmbed url={article.link} title={article.title} />
          </div>
        )}
        <Link href={`/article/${article.id}`} className="block p-3">
          <div className="flex items-start gap-2 mb-2">
            <ReadCheckbox isRead={isRead} onToggle={handleToggleRead} />
            <div className="flex-1 min-w-0">
              <p
                className={`text-xs font-medium mb-1 line-clamp-3 group-hover:text-sky-600 dark:group-hover:text-sky-400 transition-colors ${
                  isRead
                    ? "text-gray-500 dark:text-gray-400"
                    : "text-gray-900 dark:text-gray-100"
                }`}
              >
                {article.title}
              </p>
              <div className="flex items-center gap-1.5 text-xs text-gray-400 dark:text-gray-500">
                <span className="truncate">{article.feedName}</span>
                <span>·</span>
                <span className="whitespace-nowrap">{timeAgo(article.publishedAt)}</span>
              </div>
            </div>
          </div>
          {hasSummary && (
            <div className="flex items-center gap-1 text-xs text-emerald-500 dark:text-emerald-400">
              <SummarizedIcon />
              <span>Summarized</span>
            </div>
          )}
        </Link>
        <div className="px-3 pb-2 flex items-center gap-2">
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setShowResearch(true);
            }}
            className="flex-1 p-1.5 rounded text-xs text-gray-400 dark:text-gray-500 hover:text-sky-500 dark:hover:text-sky-400 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
            title="Deep Research"
          >
            <ResearchIcon />
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className={`flex-1 p-1.5 rounded transition-colors ${
              isSaved
                ? "text-sky-500"
                : "text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
            }`}
            title={isSaved ? "Unsave" : "Save"}
          >
            {isSaved ? <BookmarkFilledIcon /> : <BookmarkOutlineIcon />}
          </button>
          {isManualArticle && (
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setShowDeleteConfirm(true);
              }}
              disabled={deleting}
              className="flex-1 p-1.5 rounded transition-colors text-gray-400 dark:text-gray-500 hover:text-red-500 dark:hover:text-red-400 hover:bg-gray-50 dark:hover:bg-gray-800"
              title="Delete"
            >
              <TrashIcon />
            </button>
          )}
        </div>
        <Modal
          isOpen={showResearch}
          onClose={() => setShowResearch(false)}
          title="Deep Research"
        >
          <DeepResearch articleId={article.id} articleTitle={article.title} />
        </Modal>

        {isManualArticle &&
          createPortal(
            <Modal
              isOpen={showDeleteConfirm}
              onClose={() => setShowDeleteConfirm(false)}
              title="Delete Link"
            >
              <div className="space-y-4">
                <p className="text-gray-600 dark:text-gray-400">
                  Are you sure you want to delete this link? This action cannot be undone.
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={() => setShowDeleteConfirm(false)}
                    className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors font-medium"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleDelete}
                    disabled={deleting}
                    className="flex-1 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {deleting ? "Deleting..." : "Delete"}
                  </button>
                </div>
              </div>
            </Modal>,
            document.body
          )}
      </article>
    );
  }

  // Build the preview: AI summary if available, otherwise extract first paragraph
  const firstParagraph = article.content
    ? extractFirstParagraph(article.content)
    : null;
  const contentPreview = article.summary
    ? article.summary
    : firstParagraph
      ? truncate(firstParagraph, 280)
      : null;

  return (
    <>
      <article
        ref={cardRef}
        className={`bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-800 shadow-sm hover:shadow-md transition-shadow overflow-hidden ${
          isRead ? "opacity-75" : ""
        }`}
      >
      {isVideoArticle ? (
        <VideoEmbed url={article.link} title={article.title} className="m-4" />
      ) : article.imageUrl ? (
        <Link href={`/article/${article.id}`}>
          <div className="relative h-48 overflow-hidden">
            <img
              src={article.imageUrl}
              alt=""
              className="w-full h-full object-cover"
              loading="lazy"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = "none";
              }}
            />
          </div>
        </Link>
      ) : null}

      <div className="p-4">
        <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 mb-2">
          <ReadCheckbox isRead={isRead} onToggle={handleToggleRead} />
          <span className="font-medium">{article.feedName}</span>
          <span>&#183;</span>
          <span>{timeAgo(article.publishedAt)}</span>
          {hasSummary && (
            <>
              <span>&#183;</span>
              <span className="inline-flex items-center gap-0.5 text-emerald-600 dark:text-emerald-400" title="AI summarized">
                <SummarizedIcon />
                <span className="text-[10px] font-medium">Summarized</span>
              </span>
            </>
          )}
        </div>

        <Link href={`/article/${article.id}`}>
          <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100 line-clamp-2 hover:text-sky-600 dark:hover:text-sky-400 transition-colors leading-snug mb-2">
            {article.title}
          </h3>
        </Link>

        {contentPreview && (
          <p
            className={`text-sm mb-3 ${
              hasSummary
                ? "text-gray-600 dark:text-gray-400 line-clamp-3"
                : "text-gray-500 dark:text-gray-400 line-clamp-3"
            }`}
          >
            {contentPreview}
          </p>
        )}

        <div className="flex items-center gap-2 pt-2 border-t border-gray-50 dark:border-gray-800">
          <button
            onClick={handleSave}
            disabled={saving}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              isSaved
                ? "text-sky-600 dark:text-sky-400 bg-sky-50 dark:bg-sky-900/30 hover:bg-sky-100 dark:hover:bg-sky-900/50"
                : "text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-700 dark:hover:text-gray-200"
            }`}
            title={isSaved ? "Unsave" : "Save"}
          >
            {isSaved ? <BookmarkFilledIcon /> : <BookmarkOutlineIcon />}
            <span>{isSaved ? "Saved" : "Save"}</span>
          </button>

          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setShowResearch(!showResearch);
            }}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              showResearch
                ? "text-sky-600 dark:text-sky-400 bg-sky-50 dark:bg-sky-900/30"
                : "text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-700 dark:hover:text-gray-200"
            }`}
            title="Deep Research"
          >
            <ResearchIcon />
            <span>Research</span>
          </button>

          {isManualArticle && (
            <button
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setShowDeleteConfirm(true);
              }}
              disabled={deleting}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-gray-500 dark:text-gray-400 hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-600 dark:hover:text-red-400 transition-colors"
              title="Delete"
            >
              <TrashIcon />
              <span>Delete</span>
            </button>
          )}

          <a
            href={article.link}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-700 dark:hover:text-gray-200 transition-colors ml-auto"
          >
            <ExternalLinkIcon />
            <span>Original</span>
          </a>
        </div>

        {showResearch && (
          <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
            <DeepResearch articleId={article.id} articleTitle={article.title} />
          </div>
        )}
      </div>

    </article>

    {isManualArticle &&
      createPortal(
        <Modal
          isOpen={showDeleteConfirm}
          onClose={() => setShowDeleteConfirm(false)}
          title="Delete Link"
        >
          <div className="space-y-4">
            <p className="text-gray-600 dark:text-gray-400">
              Are you sure you want to delete this link? This action cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex-1 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {deleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </Modal>,
        document.body
      )}
  </>
  );
}
