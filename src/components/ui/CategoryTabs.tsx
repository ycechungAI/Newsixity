"use client";

import React from "react";
import { useRouter } from "next/navigation";
import type { Category } from "@/types";

interface CategoryTab {
  slug: string;
  name: string;
  total: number;
  unread: number;
}

interface CategoryTabsProps {
  categories: CategoryTab[];
  activeSlug?: string;
  basePath?: string;
  preserveParams?: Record<string, string | undefined>;
}

export default function CategoryTabs({
  categories,
  activeSlug,
  basePath = "/",
  preserveParams = {},
}: CategoryTabsProps) {
  const router = useRouter();

  const buildUrl = (categorySlug?: string) => {
    // Special case: Weather should go to dedicated weather page
    if (categorySlug === "weather" && basePath === "/") {
      return "/weather";
    }

    // Special case: Finance should go to dedicated finance page
    if (categorySlug === "finance" && basePath === "/") {
      return "/finance";
    }

    const params = new URLSearchParams();

    // Add preserved params
    Object.entries(preserveParams).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });

    // Add category param if provided
    if (categorySlug) {
      params.set("category", categorySlug);
    }

    const queryString = params.toString();
    return queryString ? `${basePath}?${queryString}` : basePath;
  };

  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
      {/* All tab */}
      <button
        onClick={() => router.push(buildUrl())}
        className={`px-4 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
          !activeSlug
            ? "bg-sky-600 text-white"
            : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
        }`}
      >
        All
      </button>

      {/* Category tabs */}
      {categories.map((cat) => (
        <React.Fragment key={cat.slug}>
          <button
            onClick={() => router.push(buildUrl(cat.slug))}
            className={`px-4 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
              activeSlug === cat.slug
                ? "bg-sky-600 text-white"
                : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
            }`}
          >
            {cat.name}
            {cat.unread > 0 && (
              <span
                className={`ml-1.5 text-xs ${
                  activeSlug === cat.slug ? "text-sky-200" : "text-gray-400 dark:text-gray-500"
                }`}
              >
                {cat.unread}
              </span>
            )}
          </button>

          {/* Finance News sub-tab */}
          {cat.slug === "finance" && basePath === "/" && (
            <button
              onClick={() => router.push("/finance/news")}
              className="px-4 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
            >
              Finance News
              {cat.unread > 0 && (
                <span className="ml-1.5 text-xs text-gray-400 dark:text-gray-500">
                  {cat.unread}
                </span>
              )}
            </button>
          )}
        </React.Fragment>
      ))}
    </div>
  );
}
