"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "@/components/ThemeProvider";
import type { Category } from "@/types";

interface SidebarProps {
  categories: (Category & { total: number; unread: number })[];
  activeSlug?: string;
}

const GlobeIcon = () => (
  <svg
    className="w-5 h-5"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <circle cx="12" cy="12" r="10" />
    <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
  </svg>
);

const ChartIcon = () => (
  <svg
    className="w-5 h-5"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <rect x="3" y="12" width="4" height="9" rx="1" />
    <rect x="10" y="7" width="4" height="14" rx="1" />
    <rect x="17" y="3" width="4" height="18" rx="1" />
  </svg>
);

const GamepadIcon = () => (
  <svg
    className="w-5 h-5"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <rect x="2" y="6" width="20" height="12" rx="6" />
    <circle cx="8" cy="12" r="1.5" fill="currentColor" />
    <circle cx="16" cy="10.5" r="1" fill="currentColor" />
    <circle cx="16" cy="13.5" r="1" fill="currentColor" />
    <circle cx="14.5" cy="12" r="1" fill="currentColor" />
    <circle cx="17.5" cy="12" r="1" fill="currentColor" />
  </svg>
);

const CpuIcon = () => (
  <svg
    className="w-5 h-5"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <rect x="5" y="5" width="14" height="14" rx="2" />
    <rect x="9" y="9" width="6" height="6" rx="1" />
    <path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3" />
  </svg>
);

const TrophyIcon = () => (
  <svg
    className="w-5 h-5"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 18.75h-9m9 0a3 3 0 0 1 3 3h-15a3 3 0 0 1 3-3m9 0v-4.5A3.375 3.375 0 0 0 13.125 10.875h-2.25A3.375 3.375 0 0 0 7.5 14.25v4.5m9-10.5V6a2.25 2.25 0 0 0-2.25-2.25h-4.5A2.25 2.25 0 0 0 7.5 6v2.25m9 0h1.125c.621 0 1.125-.504 1.125-1.125V5.25A1.125 1.125 0 0 0 17.625 4.125H16.5m-9 4.125H6.375A1.125 1.125 0 0 1 5.25 7.125V5.25A1.125 1.125 0 0 1 6.375 4.125H7.5" />
  </svg>
);

const CloudSunIcon = () => (
  <svg
    className="w-5 h-5"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15a4.5 4.5 0 0 0 4.5 4.5H18a3.75 3.75 0 0 0 .75-7.425 4.502 4.502 0 0 0-8.655-2.1A4.5 4.5 0 0 0 2.25 15Z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 2.25v1.5m5.303.97l-1.06 1.06M21.75 12h-1.5m.97 5.303l-1.06-1.06" />
  </svg>
);

const TrendingIcon = () => (
  <svg
    className="w-5 h-5"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18 9 11.25l4.306 4.306a11.95 11.95 0 0 1 5.814-5.518l2.74-1.22m0 0-5.94-2.281m5.94 2.28-2.28 5.941" />
  </svg>
);

const NewspaperIcon = () => (
  <svg
    className="w-5 h-5"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <path d="M7 7h6M7 11h10M7 15h10" />
  </svg>
);

const BookmarkIcon = () => (
  <svg
    className="w-5 h-5"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <path d="M5 5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16l-7-3.5L5 21V5z" />
  </svg>
);

const SunIcon = () => (
  <svg
    className="w-5 h-5"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
  </svg>
);

const MoonIcon = () => (
  <svg
    className="w-5 h-5"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
  </svg>
);

const ConsoleIcon = () => (
  <svg
    className="w-5 h-5"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <path strokeLinecap="round" strokeLinejoin="round" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
  </svg>
);

const SettingsIcon = () => (
  <svg
    className="w-5 h-5"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
    />
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
    />
  </svg>
);

const LinkIcon = () => (
  <svg
    className="w-5 h-5"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244"
    />
  </svg>
);

const CATEGORY_ICONS: Record<string, React.FC> = {
  "world-news": GlobeIcon,
  finance: ChartIcon,
  gaming: GamepadIcon,
  technology: CpuIcon,
  sports: TrophyIcon,
  weather: CloudSunIcon,
  "top-news": TrendingIcon,
  others: LinkIcon,
};

export default function Sidebar({ categories, activeSlug }: SidebarProps) {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();

  // Maintain local unread counts so they update live when articles are read
  const [unreadCounts, setUnreadCounts] = useState<Record<string, number>>(() => {
    const counts: Record<string, number> = {};
    for (const cat of categories) {
      counts[cat.slug] = cat.unread;
    }
    return counts;
  });

  // Sync local state when server-side categories prop changes (e.g. after feed refresh)
  useEffect(() => {
    const counts: Record<string, number> = {};
    for (const cat of categories) {
      counts[cat.slug] = cat.unread;
    }
    setUnreadCounts(counts);
  }, [categories]);

  // Listen for "article-read" and "article-unread" custom events dispatched by ArticleCard
  useEffect(() => {
    function handleArticleRead(e: Event) {
      const detail = (e as CustomEvent).detail as {
        articleId: number;
        categorySlug: string | null;
      };
      if (detail.categorySlug) {
        setUnreadCounts((prev) => ({
          ...prev,
          [detail.categorySlug!]: Math.max(0, (prev[detail.categorySlug!] ?? 0) - 1),
        }));
      }
    }

    function handleArticleUnread(e: Event) {
      const detail = (e as CustomEvent).detail as {
        articleId: number;
        categorySlug: string | null;
      };
      if (detail.categorySlug) {
        setUnreadCounts((prev) => ({
          ...prev,
          [detail.categorySlug!]: (prev[detail.categorySlug!] ?? 0) + 1,
        }));
      }
    }

    window.addEventListener("article-read", handleArticleRead);
    window.addEventListener("article-unread", handleArticleUnread);
    return () => {
      window.removeEventListener("article-read", handleArticleRead);
      window.removeEventListener("article-unread", handleArticleUnread);
    };
  }, []);

  const isAllActive = !activeSlug && pathname === "/";
  const isSavedActive = pathname === "/saved";
  const isConsoleActive = pathname === "/console";
  const isSettingsActive = pathname === "/settings";

  return (
    <aside className="w-64 h-screen bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 flex flex-col fixed left-0 top-0 z-30">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-gray-100 dark:border-gray-800">
        <Link href="/" className="text-xl font-bold text-sky-600 dark:text-sky-400 tracking-tight">
          Newsixity
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3 px-3">
        {/* All News */}
        <Link
          href="/"
          className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors mb-1 ${
            isAllActive
              ? "bg-sky-50 dark:bg-sky-900/30 text-sky-600 dark:text-sky-400 border-l-2 border-sky-500"
              : "text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
          }`}
        >
          <NewspaperIcon />
          <span className="flex-1">All News</span>
        </Link>

        {/* Category links */}
        <div className="mt-2 space-y-0.5">
          {categories.map((cat) => {
            const isActive =
              activeSlug === cat.slug ||
              (cat.slug === "weather" && pathname === "/weather") ||
              (cat.slug === "finance" && pathname === "/finance");
            const IconComponent = CATEGORY_ICONS[cat.slug] || GlobeIcon;
            const unread = unreadCounts[cat.slug] ?? 0;

            // Special handling for finance - goes to stock dashboard
            let href = `/category/${cat.slug}`;
            if (cat.slug === "weather") href = "/weather";
            if (cat.slug === "finance") href = "/finance";

            return (
              <div key={cat.id}>
                <Link
                  href={href}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-sky-50 dark:bg-sky-900/30 text-sky-600 dark:text-sky-400 border-l-2 border-sky-500"
                      : "text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                  }`}
                >
                  <IconComponent />
                  <span className="flex-1">{cat.name}</span>
                  {cat.slug !== "finance" && unread > 0 && (
                    <span className="bg-sky-500 text-white text-xs font-semibold rounded-full min-w-[20px] h-5 flex items-center justify-center px-1.5">
                      {unread > 99 ? "99+" : unread}
                    </span>
                  )}
                </Link>

                {/* Finance News sub-item */}
                {cat.slug === "finance" && (
                  <Link
                    href="/finance/news"
                    className={`flex items-center gap-3 pl-11 pr-3 py-2 rounded-lg text-sm font-medium transition-colors mt-0.5 ${
                      pathname === "/finance/news"
                        ? "bg-sky-50 dark:bg-sky-900/30 text-sky-600 dark:text-sky-400"
                        : "text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
                    }`}
                  >
                    <NewspaperIcon />
                    <span className="flex-1">Finance News</span>
                    {unread > 0 && (
                      <span className="bg-sky-500 text-white text-xs font-semibold rounded-full min-w-[20px] h-5 flex items-center justify-center px-1.5">
                        {unread > 99 ? "99+" : unread}
                      </span>
                    )}
                  </Link>
                )}
              </div>
            );
          })}
        </div>
      </nav>

      {/* Bottom section: console, settings, saved, theme toggle */}
      <div className="border-t border-gray-100 dark:border-gray-800 px-3 py-3 space-y-1">
        <Link
          href="/console"
          className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
            isConsoleActive
              ? "bg-sky-50 dark:bg-sky-900/30 text-sky-600 dark:text-sky-400 border-l-2 border-sky-500"
              : "text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
          }`}
        >
          <ConsoleIcon />
          <span className="flex-1">Console</span>
        </Link>

        <Link
          href="/settings"
          className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
            isSettingsActive
              ? "bg-sky-50 dark:bg-sky-900/30 text-sky-600 dark:text-sky-400 border-l-2 border-sky-500"
              : "text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
          }`}
        >
          <SettingsIcon />
          <span className="flex-1">Settings</span>
        </Link>

        <Link
          href="/saved"
          className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
            isSavedActive
              ? "bg-sky-50 dark:bg-sky-900/30 text-sky-600 dark:text-sky-400 border-l-2 border-sky-500"
              : "text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
          }`}
        >
          <BookmarkIcon />
          <span className="flex-1">Saved</span>
        </Link>

        {/* Dark mode toggle */}
        <button
          onClick={toggleTheme}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 w-full"
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? <SunIcon /> : <MoonIcon />}
          <span className="flex-1 text-left">
            {theme === "dark" ? "Light Mode" : "Dark Mode"}
          </span>
        </button>
      </div>
    </aside>
  );
}
