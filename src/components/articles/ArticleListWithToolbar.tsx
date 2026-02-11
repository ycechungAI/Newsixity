"use client";

import { useState } from "react";
import type { Article, ArticleGroup as ArticleGroupType } from "@/types";
import ArticleList, { type ViewMode } from "./ArticleList";
import ReadToggleToolbar from "../ui/ReadToggleToolbar";

interface ArticleListWithToolbarProps {
  articles?: Article[];
  groups?: ArticleGroupType[];
  viewMode?: ViewMode;
  emptyMessage?: string;
  categorySlug?: string | null;
  unreadCount: number;
}

export default function ArticleListWithToolbar({
  articles,
  groups,
  viewMode = "topics",
  emptyMessage,
  categorySlug,
  unreadCount,
}: ArticleListWithToolbarProps) {
  const [autoMarkRead, setAutoMarkRead] = useState(true);

  return (
    <>
      <ReadToggleToolbar
        autoMarkRead={autoMarkRead}
        onAutoMarkReadChange={setAutoMarkRead}
        unreadCount={unreadCount}
        categorySlug={categorySlug}
      />
      <ArticleList
        articles={articles}
        groups={groups}
        viewMode={viewMode}
        emptyMessage={emptyMessage}
        autoMarkRead={autoMarkRead}
      />
    </>
  );
}
