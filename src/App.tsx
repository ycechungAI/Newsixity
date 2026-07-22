import { useCallback, useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import type { Category } from "@/types";
import Sidebar from "@/components/layout/Sidebar";
import TopBar from "@/components/layout/TopBar";
import ThemeProvider from "@/components/ThemeProvider";
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

  useEffect(() => {
    window.addEventListener("feeds-refreshed", fetchCategories);
    return () => window.removeEventListener("feeds-refreshed", fetchCategories);
  }, [fetchCategories]);

  return (
    <ThemeProvider>
      <div className="layout">
        <Sidebar categories={categories} />
        <div className="main">
          <TopBar />
          <Outlet />
        </div>
      </div>
    </ThemeProvider>
  );
}
