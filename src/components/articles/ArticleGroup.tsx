"use client";

import { useEffect, useState } from "react";
import type { ArticleGroup as ArticleGroupType } from "@/types";
import ArticleCard from "./ArticleCard";

interface ArticleGroupProps {
  group: ArticleGroupType;
  autoMarkRead?: boolean;
}

/**
 * One topic: the representative article plus the other sources covering the
 * same story, collapsed by default — collapsing duplicates is the point of
 * the Topics view. Every article keeps its own ArticleCard controls; they
 * act on that one article, not the whole group.
 */
export default function ArticleGroup({ group, autoMarkRead = true }: ArticleGroupProps) {
  const [expanded, setExpanded] = useState(false);
  const [deleted, setDeleted] = useState<Set<number>>(new Set());

  // ArticleCard hides itself on delete, but the group would linger with a
  // stale "N more sources" count — or as an empty shell once every article
  // in it is gone.
  useEffect(() => {
    const onDeleted = (e: Event) => {
      const id = (e as CustomEvent<{ id: number }>).detail?.id;
      if (id != null) setDeleted((prev) => new Set(prev).add(id));
    };
    window.addEventListener("article-deleted", onDeleted);
    return () => window.removeEventListener("article-deleted", onDeleted);
  }, []);

  const live = group.articles.filter((a) => !deleted.has(a.id));
  if (live.length === 0) return null;
  const lead = live.find((a) => a.id === group.representativeId) ?? live[0];
  const others = live.filter((a) => a.id !== lead.id);

  return (
    <div className={`topic-group${others.length > 0 ? " is-topic" : ""}`}>
      {group.label && <div className="group-label">{group.label}</div>}
      <ul className="article-list">
        <ArticleCard key={lead.id} article={lead} autoMarkRead={autoMarkRead} />
      </ul>
      {others.length > 0 && (
        <>
          {expanded && (
            <ul className="article-list group-others">
              {others.map((a) => <ArticleCard key={a.id} article={a} autoMarkRead={autoMarkRead} />)}
            </ul>
          )}
          <button className="group-more-btn" onClick={() => setExpanded((e) => !e)}>
            {expanded
              ? `▲ hide ${others.length} related`
              : `▼ ${others.length} more source${others.length !== 1 ? "s" : ""} on this story`}
          </button>
        </>
      )}
    </div>
  );
}
