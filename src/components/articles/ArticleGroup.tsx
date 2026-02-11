"use client";

import { useState } from "react";
import type { ArticleGroup as ArticleGroupType } from "@/types";
import ArticleCard from "./ArticleCard";

interface ArticleGroupProps {
  group: ArticleGroupType;
}

const ChevronIcon = ({ expanded }: { expanded: boolean }) => (
  <svg
    className={`w-4 h-4 transition-transform ${expanded ? "rotate-180" : ""}`}
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={2}
  >
    <path d="M6 9l6 6 6-6" />
  </svg>
);

export default function ArticleGroup({ group }: ArticleGroupProps) {
  const otherArticles = group.articles.filter(
    (a) => a.id !== group.representativeId
  );
  const defaultExpanded = otherArticles.length <= 2;
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div className="rounded-xl border border-gray-100 dark:border-gray-800 overflow-hidden shadow-sm hover:shadow-md transition-shadow">
      {group.label && (
        <div className="bg-gray-50 dark:bg-gray-800 px-4 py-1.5 border-b border-gray-100 dark:border-gray-700">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
            {group.label}
          </span>
        </div>
      )}

      <ArticleCard article={group.representative} />

      {otherArticles.length > 0 && (
        <div className="bg-gray-50/50 dark:bg-gray-800/50">
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full flex items-center justify-between px-4 py-2.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100/50 dark:hover:bg-gray-700/50 transition-colors"
          >
            <span className="font-medium">
              {group.articleCount} source{group.articleCount !== 1 ? "s" : ""}
            </span>
            <ChevronIcon expanded={expanded} />
          </button>

          {expanded && (
            <div className="bg-white dark:bg-gray-900">
              {otherArticles.map((article) => (
                <ArticleCard
                  key={article.id}
                  article={article}
                  compact
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
