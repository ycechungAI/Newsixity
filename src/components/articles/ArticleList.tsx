"use client";

import type { Article, ArticleGroup as ArticleGroupType } from "@/types";
import ArticleCard from "./ArticleCard";
import ArticleGroup from "./ArticleGroup";
import ArticlesBySource from "./ArticlesBySource";
import ArticlesByDate from "./ArticlesByDate";
import ArticlesByCategory from "./ArticlesByCategory";
import EmptyState from "../ui/EmptyState";

export type ViewMode = "topics" | "compact" | "sources" | "timeline" | "list" | "categories";

interface ArticleListProps {
  articles?: Article[];
  groups?: ArticleGroupType[];
  viewMode?: ViewMode;
  emptyMessage?: string;
  autoMarkRead?: boolean;
}

function flattenArticles(
  articles?: Article[],
  groups?: ArticleGroupType[]
): Article[] {
  if (articles && articles.length > 0) return articles;
  if (groups && groups.length > 0) {
    const seen = new Set<number>();
    const flat: Article[] = [];
    for (const group of groups) {
      for (const article of group.articles) {
        if (!seen.has(article.id)) {
          seen.add(article.id);
          flat.push(article);
        }
      }
    }
    return flat;
  }
  return [];
}

export default function ArticleList({
  articles,
  groups,
  viewMode = "topics",
  emptyMessage,
  autoMarkRead = true,
}: ArticleListProps) {
  // List view: flat email-inbox-style rows
  if (viewMode === "list") {
    const allArticles = flattenArticles(articles, groups);
    if (allArticles.length === 0) {
      return (
        <EmptyState
          title={emptyMessage || "No articles yet"}
          description="Refresh your feeds to fetch the latest articles."
        />
      );
    }

    return (
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-800 overflow-hidden">
        {allArticles.map((article) => (
          <ArticleCard
            key={article.id}
            article={article}
            listView
            autoMarkRead={autoMarkRead}
          />
        ))}
      </div>
    );
  }

  // Compact view: 5-column dense grid without descriptions
  if (viewMode === "compact") {
    const allArticles = flattenArticles(articles, groups);
    if (allArticles.length === 0) {
      return (
        <EmptyState
          title={emptyMessage || "No articles yet"}
          description="Refresh your feeds to fetch the latest articles."
        />
      );
    }

    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
        {allArticles.map((article) => (
          <ArticleCard
            key={article.id}
            article={article}
            compact
            autoMarkRead={autoMarkRead}
          />
        ))}
      </div>
    );
  }

  // Grouped views: categories, sources, timeline
  if (viewMode === "categories" || viewMode === "sources" || viewMode === "timeline") {
    const allArticles = flattenArticles(articles, groups);
    if (allArticles.length === 0) {
      return (
        <EmptyState
          title={emptyMessage || "No articles yet"}
          description="Refresh your feeds to fetch the latest articles."
        />
      );
    }

    if (viewMode === "categories") {
      return <ArticlesByCategory articles={allArticles} />;
    }
    if (viewMode === "sources") {
      return <ArticlesBySource articles={allArticles} />;
    }
    return <ArticlesByDate articles={allArticles} />;
  }

  // Topics view (default): render grouped articles
  if (groups && groups.length > 0) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {groups.map((group) => (
          <ArticleGroup key={group.id} group={group} />
        ))}
      </div>
    );
  }

  // Render flat article list (cards grid)
  if (articles && articles.length > 0) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {articles.map((article) => (
          <ArticleCard key={article.id} article={article} autoMarkRead={autoMarkRead} />
        ))}
      </div>
    );
  }

  // Empty state
  return (
    <EmptyState
      title={emptyMessage || "No articles yet"}
      description="Refresh your feeds to fetch the latest articles."
    />
  );
}
