"use client";

import type { Article } from "@/types";
import ArticleCard from "./ArticleCard";

interface ArticlesBySourceProps {
  articles: Article[];
}

export default function ArticlesBySource({ articles }: ArticlesBySourceProps) {
  const sourceMap = new Map<string, Article[]>();

  for (const article of articles) {
    const source = article.feedName || "Unknown Source";
    if (!sourceMap.has(source)) {
      sourceMap.set(source, []);
    }
    sourceMap.get(source)!.push(article);
  }

  const sortedSources = Array.from(sourceMap.entries()).sort(([a], [b]) =>
    a.localeCompare(b)
  );

  for (const [, sourceArticles] of sortedSources) {
    sourceArticles.sort((a, b) => {
      const dateA = a.publishedAt ? new Date(a.publishedAt).getTime() : 0;
      const dateB = b.publishedAt ? new Date(b.publishedAt).getTime() : 0;
      return dateB - dateA;
    });
  }

  return (
    <div className="space-y-8">
      {sortedSources.map(([source, sourceArticles]) => (
        <section key={source}>
          <div className="mb-3 flex items-center gap-2">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{source}</h2>
            <span className="rounded-full bg-gray-100 dark:bg-gray-800 px-2.5 py-0.5 text-xs font-medium text-gray-500 dark:text-gray-400">
              {sourceArticles.length}
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {sourceArticles.map((article) => (
              <ArticleCard key={article.id} article={article} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
