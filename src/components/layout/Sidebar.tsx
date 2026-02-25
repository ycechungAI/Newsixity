"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "@/components/ThemeProvider";
import type { Category } from "@/types";

interface SidebarProps {
  categories: (Category & { total: number; unread: number })[];
}

const LABELS: Record<string, string> = {
  "world-news": "World",
  finance:      "Finance",
  gaming:       "Gaming",
  technology:   "Tech",
  sports:       "Sports",
  weather:      "Weather",
  "top-news":   "Top News",
  others:       "Other",
};

const MIN_W = 24;
const MAX_W = 400;
const DEFAULT_W = 156;

export default function Sidebar({ categories }: SidebarProps) {
  const pathname = usePathname();
  const { toggleTheme } = useTheme();
  const [collapsed, setCollapsed] = useState(true);
  const [width, setWidth] = useState(DEFAULT_W);
  const [dragging, setDragging] = useState(false);
  const sidebarRef = useRef<HTMLElement>(null);
  const dragStart = useRef<{ x: number; w: number } | null>(null);

  const [unreadAdjustments, setUnreadAdjustments] = useState<Record<string, number>>({});
  const unreadCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const cat of categories) {
      const adjustment = unreadAdjustments[cat.slug] ?? 0;
      counts[cat.slug] = Math.max(0, cat.unread + adjustment);
    }
    return counts;
  }, [categories, unreadAdjustments]);

  useEffect(() => {
    function onRead(e: Event) {
      const { categorySlug } = (e as CustomEvent).detail;
      if (categorySlug)
        setUnreadAdjustments((prev) => ({
          ...prev,
          [categorySlug]: (prev[categorySlug] ?? 0) - 1,
        }));
    }
    function onUnread(e: Event) {
      const { categorySlug } = (e as CustomEvent).detail;
      if (categorySlug)
        setUnreadAdjustments((prev) => ({
          ...prev,
          [categorySlug]: (prev[categorySlug] ?? 0) + 1,
        }));
    }
    window.addEventListener("article-read", onRead);
    window.addEventListener("article-unread", onUnread);
    return () => {
      window.removeEventListener("article-read", onRead);
      window.removeEventListener("article-unread", onUnread);
    };
  }, []);

  // Drag resize logic
  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragStart.current = { x: e.clientX, w: width };
    setDragging(true);
  }, [width]);

  useEffect(() => {
    if (!dragging) return;

    function onMove(e: MouseEvent) {
      if (!dragStart.current) return;
      const delta = e.clientX - dragStart.current.x;
      const newW = Math.min(MAX_W, Math.max(MIN_W, dragStart.current.w + delta));
      setWidth(newW);
      if (newW <= MIN_W + 12) setCollapsed(true);
      else setCollapsed(false);
    }

    function onUp() {
      setDragging(false);
      dragStart.current = null;
    }

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [dragging]);

  const effectiveWidth = collapsed ? MIN_W : width;

  return (
    <aside
      ref={sidebarRef}
      className={`sidebar${collapsed ? " collapsed" : ""}`}
      style={{ width: effectiveWidth, minWidth: effectiveWidth, transition: dragging ? "none" : "width .12s" }}
    >
      <div className="sb-head">
        {!collapsed && (
          <Link href="/" className="sb-logo" style={{ textDecoration: "none" }}>
            Newsixity
          </Link>
        )}
        <button
          className="sb-toggle"
          onClick={() => {
            if (collapsed) { setCollapsed(false); setWidth(DEFAULT_W); }
            else setCollapsed(true);
          }}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? "»" : "«"}
        </button>
      </div>

      {/* nav-body: in DOM always — terminal browsers see links even when CSS hides it */}
      <div className="nav-body">
        <span className="nav-section-label">News</span>
        <Link href="/" className={`nav-link${pathname === "/" ? " active" : ""}`}>All News</Link>

        {categories.map((cat) => {
          const isActive =
            pathname === `/category/${cat.slug}` ||
            (cat.slug === "weather" && pathname === "/weather") ||
            (cat.slug === "finance" && pathname === "/finance");

          let href = `/category/${cat.slug}`;
          if (cat.slug === "weather") href = "/weather";
          if (cat.slug === "finance") href = "/finance";

          const unread = unreadCounts[cat.slug] ?? 0;
          const label = LABELS[cat.slug] ?? cat.name;

          return (
            <div key={cat.id}>
              <Link href={href} className={`nav-link${isActive ? " active" : ""}`}>
                <span>{label}</span>
                {cat.slug !== "finance" && unread > 0 && (
                  <span className="nav-badge">{unread > 99 ? "99+" : unread}</span>
                )}
              </Link>
              {cat.slug === "finance" && (
                <Link href="/finance/news" className={`nav-link sub${pathname === "/finance/news" ? " active" : ""}`}>
                  <span>↳ News</span>
                  {unread > 0 && <span className="nav-badge">{unread > 99 ? "99+" : unread}</span>}
                </Link>
              )}
            </div>
          );
        })}

        <span className="nav-section-label" style={{ marginTop: 8 }}>Library</span>
        <Link href="/saved" className={`nav-link${pathname === "/saved" ? " active" : ""}`}>Saved</Link>
      </div>

      <div className="sb-footer">
        <Link href="/settings" className={`nav-link${pathname === "/settings" ? " active" : ""}`}>Settings</Link>
        <Link href="/console"  className={`nav-link${pathname === "/console"  ? " active" : ""}`}>Console</Link>
        <button
          className="nav-link"
          onClick={toggleTheme}
          style={{ width: "100%", textAlign: "left", background: "none", border: "none", cursor: "pointer" }}
          title="Toggle theme"
        >
          Toggle Theme
        </button>
      </div>

      {/* Drag handle — right edge */}
      {!collapsed && (
        <div
          className={`sb-resize-handle${dragging ? " dragging" : ""}`}
          onMouseDown={onMouseDown}
          title="Drag to resize"
        />
      )}
    </aside>
  );
}
