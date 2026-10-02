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

/**
 * Topic groups from the articles' own groupId, keeping the list's order (a
 * group sits where its first article would). Built client-side from the
 * page that was already fetched, so pagination, filters and unread counts
 * mean the same thing in every view.
 */
function topicGroups(articles: Article[]): ArticleGroupType[] {
  const byKey = new Map<string, Article[]>();
  for (const a of articles) {
    const key = a.groupId != null ? `g${a.groupId}` : `a${a.id}`;
    const members = byKey.get(key);
    if (members) members.push(a);
    else byKey.set(key, [a]);
  }
  return Array.from(byKey.values()).map((members) => ({
    id: members[0].groupId ?? -members[0].id,
    label: null,
    categoryId: 0,
    representativeId: members[0].id,
    articleCount: members.length,
    representative: members[0],
    articles: members,
  }));
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

  const all = flatten(articles, groups);
  if (all.length === 0) return <Empty message={emptyMessage} />;

  // Topics view — the same story from several sources collapses into one.
  // No page passed `groups` before, so this view silently rendered a flat
  // list; it now groups whatever articles it is given.
  if (viewMode === "topics") {
    const topics = groups?.length ? groups : topicGroups(all);
    return (
      <div>
        {topics.map(g => <ArticleGroup key={g.id} group={g} autoMarkRead={autoMarkRead} />)}
      </div>
    );
  }

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

  // All other views (list, compact) — flat list
  return (
    <ul className="article-list">
      {all.map(a => <ArticleCard key={a.id} article={a} autoMarkRead={autoMarkRead} />)}
    </ul>
  );
}
