import { useCallback, useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import type { Category } from "@/types";
import Sidebar from "@/components/layout/Sidebar";
import TopBar from "@/components/layout/TopBar";
import ThemeProvider from "@/components/ThemeProvider";
import { VideoPlayerProvider } from "@/components/video/VideoPlayerHost";
import { installExternalLinkHandler } from "@/lib/ui/externalLinks";
import "./app/globals.css";

interface CategoryWithCounts extends Category {
  total: number;
  unread: number;
}

export default function App() {
  const [categories, setCategories] = useState<CategoryWithCounts[]>([]);

  const fetchCategories = useCallback(() => {
    fetch("/api/categories")
      .then((r) => r.json())
      .then((cats: CategoryWithCounts[]) => {
        setCategories(cats || []);
      });
  }, []);

  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  // Off-site links must reach the real browser; in the packaged app's
  // WKWebView target="_blank" is silently a no-op. See externalLinks.ts.
  useEffect(() => installExternalLinkHandler(), []);

  useEffect(() => {
    window.addEventListener("feeds-refreshed", fetchCategories);
    return () => window.removeEventListener("feeds-refreshed", fetchCategories);
  }, [fetchCategories]);

  return (
    <ThemeProvider>
      {/* Wraps the router so a playing video survives navigation. */}
      <VideoPlayerProvider>
        <div className="layout">
          <Sidebar categories={categories} />
          <div className="main">
            <TopBar />
            <Outlet />
          </div>
        </div>
      </VideoPlayerProvider>
    </ThemeProvider>
  );
}
