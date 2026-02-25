"use client";

import type { Article } from "@/types";
import ArticleCard from "./ArticleCard";

interface ArticlesByDateProps {
  articles: Article[];
}

type DateBucket = "Today" | "Yesterday" | "This Week" | "Older";

function getDateBucket(publishedAt: string | null): DateBucket {
  if (!publishedAt) return "Older";

  const now = new Date();
  const published = new Date(publishedAt);
  const diffMs = now.getTime() - published.getTime();
  const diffHours = diffMs / (1000 * 60 * 60);

  if (diffHours < 24) return "Today";
  if (diffHours < 48) return "Yesterday";
  if (diffHours < 168) return "This Week";
  return "Older";
}

const BUCKET_ORDER: DateBucket[] = ["Today", "Yesterday", "This Week", "Older"];

export default function ArticlesByDate({ articles }: ArticlesByDateProps) {
  const bucketMap = new Map<DateBucket, Article[]>();

  for (const bucket of BUCKET_ORDER) {
    bucketMap.set(bucket, []);
  }

  for (const article of articles) {
    const bucket = getDateBucket(article.publishedAt);
    bucketMap.get(bucket)!.push(article);
  }

  for (const [, bucketArticles] of bucketMap) {
    bucketArticles.sort((a, b) => {
      const dateA = a.publishedAt ? new Date(a.publishedAt).getTime() : 0;
      const dateB = b.publishedAt ? new Date(b.publishedAt).getTime() : 0;
      return dateB - dateA;
    });
  }

  const nonEmptyBuckets = BUCKET_ORDER.filter(
    (bucket) => bucketMap.get(bucket)!.length > 0
  );

  return (
    <div className="space-y-8">
      {nonEmptyBuckets.map((bucket) => {
        const bucketArticles = bucketMap.get(bucket)!;
        return (
          <section key={bucket}>
            <div className="mb-3 flex items-center gap-2">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{bucket}</h2>
              <span className="rounded-full bg-gray-100 dark:bg-gray-800 px-2.5 py-0.5 text-xs font-medium text-gray-500 dark:text-gray-400">
                {bucketArticles.length}
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {bucketArticles.map((article) => (
                <ArticleCard key={article.id} article={article} />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
