"use client";

import type { Article, ArticleGroup as ArticleGroupType } from "@/types";
import ArticleCard from "./ArticleCard";
import ArticleGroup from "./ArticleGroup";

export type ViewMode = "topics" | "cards" | "compact" | "sources" | "timeline" | "list" | "categories";

interface ArticleListProps {
  articles?: Article[];
  groups?: ArticleGroupType[];
  viewMode?: ViewMode;
  emptyMessage?: string;
  autoMarkRead?: boolean;
}

function flatten(articles?: Article[], groups?: ArticleGroupType[]): Article[] {
  if (articles?.length) return articles;
  if (groups?.length) {
    const seen = new Set<number>();
    const out: Article[] = [];
    for (const g of groups) {
      for (const a of g.articles) {
        if (!seen.has(a.id)) { seen.add(a.id); out.push(a); }
      }
    }
    return out;
  }
  return [];
}

function groupBy<T>(arr: T[], key: (item: T) => string): [string, T[]][] {
  const map = new Map<string, T[]>();
  for (const item of arr) {
    const k = key(item);
    if (!map.has(k)) map.set(k, []);
    map.get(k)!.push(item);
  }
  return Array.from(map.entries());
}

function Empty({ message }: { message?: string }) {
  return (
    <div className="empty">
      <div className="empty-title">{message ?? "No articles yet"}</div>
      <div className="empty-desc">Refresh your feeds to fetch the latest articles.</div>
    </div>
  );
}

export default function ArticleList({
  articles,
  groups,
  viewMode = "topics",
  emptyMessage,
  autoMarkRead = true,
}: ArticleListProps) {

  // Cards view — 3-column image grid
  if (viewMode === "cards") {
    const all = flatten(articles, groups);
    if (all.length === 0) return <Empty message={emptyMessage} />;
    return (
      <div className="card-grid">
        {all.map(a => <ArticleCard key={a.id} article={a} autoMarkRead={autoMarkRead} cardView />)}
      </div>
    );
  }

  // Topics view — grouped articles
  if (viewMode === "topics" && groups && groups.length > 0) {
    return (
      <div>
        {groups.map(g => <ArticleGroup key={g.id} group={g} />)}
      </div>
    );
  }

  const all = flatten(articles, groups);
  if (all.length === 0) return <Empty message={emptyMessage} />;

  // Sources view — grouped by feed name (sorted alphabetically)
  if (viewMode === "sources") {
    const bySource = groupBy(all, a => a.feedName ?? "Unknown");
    bySource.sort((a, b) => a[0].localeCompare(b[0]));
    return (
      <div>
        {bySource.map(([src, arts]) => (
          <div key={src} className="article-group">
            <div className="group-label">{src}</div>
            <ul className="article-list">
              {arts.map(a => <ArticleCard key={a.id} article={a} autoMarkRead={autoMarkRead} />)}
            </ul>
          </div>
        ))}
      </div>
    );
  }

  // Timeline view — grouped by date
  if (viewMode === "timeline") {
    const byDate = groupBy(all, a => {
      const d = new Date(a.publishedAt ?? a.fetchedAt);
      return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
    });
    return (
      <div>
        {byDate.map(([date, arts]) => (
          <div key={date} className="article-group">
            <div className="group-label">{date}</div>
            <ul className="article-list">
              {arts.map(a => <ArticleCard key={a.id} article={a} autoMarkRead={autoMarkRead} />)}
            </ul>
          </div>
        ))}
      </div>
    );
  }

  // All other views (list, compact, flat topics fallback) — flat list
  return (
    <ul className="article-list">
      {all.map(a => <ArticleCard key={a.id} article={a} autoMarkRead={autoMarkRead} />)}
    </ul>
  );
}
