"use client";

import "./globals.css";
import type { Article, Category } from "@/types";
import Sidebar from "@/components/layout/Sidebar";
import TopBar from "@/components/layout/TopBar";
import ThemeProvider from "@/components/ThemeProvider";
import { useEffect, useState } from "react";

interface CategoryWithCounts extends Category {
  total: number;
  unread: number;
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [categories, setCategories] = useState<CategoryWithCounts[]>([]);

  useEffect(() => {
    Promise.all([
      fetch("/api/categories").then(r => r.json()),
      fetch("/api/articles?limit=1000").then(r => r.json()),
    ])
      .then(([cats, articles]: [Category[], Article[]]) => {
        const counts = new Map<string, { total: number; unread: number }>();
        (cats || []).forEach((cat: Category) => {
          counts.set(cat.slug, { total: 0, unread: 0 });
        });
        (articles || []).forEach((art: Article) => {
          const entry = counts.get(art.categorySlug);
          if (entry) {
            entry.total++;
            if (!art.isRead) entry.unread++;
          }
        });

        const withCounts: CategoryWithCounts[] = (cats || []).map((cat: Category) => {
          const c = counts.get(cat.slug) || { total: 0, unread: 0 };
          return {
            ...cat,
            ...c,
          };
        });
        setCategories(withCounts);
      });
  }, []);

  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider>
          <div className="layout">
            <Sidebar categories={categories} />
            <div className="main">
              <TopBar />
              {children}
            </div>
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
