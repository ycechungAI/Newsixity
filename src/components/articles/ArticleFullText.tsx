"use client";

import { useState } from "react";

interface ArticleFullTextProps {
  /** Stored article text. May be a feed teaser or a scraped page body. */
  content: string | null;
  /** Canonical article URL, for the link out. */
  link?: string | null;
}

/**
 * Full-text disclosure for the article page.
 *
 * The text used to render unconditionally below the summary, so a long article
 * buried everything under it. It now sits behind a toggle, with the
 * "Read Original Article" link immediately beneath so it's reachable without
 * expanding anything — that link is the real fallback when the stored text is
 * a teaser or the page has gone stale.
 */
export default function ArticleFullText({ content, link }: ArticleFullTextProps) {
  const [open, setOpen] = useState(false);

  if (!content) return null;

  const charCount = content.length;
  // Feeds ship a paragraph or two; anything much longer was scraped from the
  // article page and is worth opening properly.
  const looksLikeTeaser = charCount < 1500;

  return (
    <div className="article-fulltext">
      <button
        type="button"
        className="article-fulltext-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span>
          {open ? "Hide full text" : "Show full text"}
          <span className="article-fulltext-meta">
            {charCount.toLocaleString()} characters
            {looksLikeTeaser ? " · excerpt from feed" : " · full article"}
          </span>
        </span>
        <span className="article-fulltext-caret" aria-hidden="true">
          {open ? "▲" : "▼"}
        </span>
      </button>

      {open && <div className="prose article-fulltext-body">{content}</div>}

      {link && (
        <a
          href={link}
          target="_blank"
          rel="noopener noreferrer"
          className="article-open-btn"
        >
          ↗ Read Original Article
        </a>
      )}
    </div>
  );
}