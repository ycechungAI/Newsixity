"use client";

import { useState } from "react";
import type { ArticleGroup as ArticleGroupType } from "@/types";
import ArticleCard from "./ArticleCard";

interface ArticleGroupProps {
  group: ArticleGroupType;
}

export default function ArticleGroup({ group }: ArticleGroupProps) {
  const others = group.articles.filter(a => a.id !== group.representativeId);
  const [expanded, setExpanded] = useState(others.length <= 3);

  return (
    <div className="article-group">
      {group.label && <div className="group-label">{group.label}</div>}
      <ul className="article-list">
        <ArticleCard article={group.representative} />
        {expanded && others.map(a => <ArticleCard key={a.id} article={a} />)}
      </ul>
      {others.length > 0 && (
        <button className="group-more-btn" onClick={() => setExpanded(e => !e)}>
          {expanded
            ? `▲ hide ${others.length} related`
            : `▼ ${others.length} more source${others.length !== 1 ? "s" : ""}`}
        </button>
      )}
    </div>
  );
}
