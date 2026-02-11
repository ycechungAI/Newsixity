"use client";

import type { Article } from "@/types";
import ArticleCard from "./ArticleCard";

interface ArticlesByCategoryProps {
  articles: Article[];
}

function formatCategoryName(slug: string): string {
  return slug.charAt(0).toUpperCase() + slug.slice(1).replace(/-/g, " ");
}

export default function ArticlesByCategory({ articles }: ArticlesByCategoryProps) {
  const categoryMap = new Map<string, Article[]>();

  for (const article of articles) {
    const cat = article.categorySlug || "uncategorized";
    if (!categoryMap.has(cat)) {
      categoryMap.set(cat, []);
    }
    categoryMap.get(cat)!.push(article);
  }

  const sortedCategories = Array.from(categoryMap.entries()).sort(([a], [b]) =>
    a.localeCompare(b)
  );

  for (const [, catArticles] of sortedCategories) {
    catArticles.sort((a, b) => {
      const dateA = a.publishedAt ? new Date(a.publishedAt).getTime() : 0;
      const dateB = b.publishedAt ? new Date(b.publishedAt).getTime() : 0;
      return dateB - dateA;
    });
  }

  return (
    <div className="space-y-8">
      {sortedCategories.map(([category, catArticles]) => (
        <section key={category}>
          <div className="mb-3 flex items-center gap-2">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {formatCategoryName(category)}
            </h2>
            <span className="rounded-full bg-gray-100 dark:bg-gray-800 px-2.5 py-0.5 text-xs font-medium text-gray-500 dark:text-gray-400">
              {catArticles.length}
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {catArticles.map((article) => (
              <ArticleCard key={article.id} article={article} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
