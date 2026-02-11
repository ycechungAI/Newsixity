"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";

type ViewMode = "topics" | "compact" | "sources" | "timeline" | "list";

interface ViewModeToggleProps {
  viewMode: ViewMode;
}

const MODES: { value: ViewMode; label: string; icon: React.ReactNode }[] = [
  {
    value: "topics",
    label: "Topics",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 0 1 6 3.75h2.25A2.25 2.25 0 0 1 10.5 6v2.25a2.25 2.25 0 0 1-2.25 2.25H6a2.25 2.25 0 0 1-2.25-2.25V6ZM3.75 15.75A2.25 2.25 0 0 1 6 13.5h2.25a2.25 2.25 0 0 1 2.25 2.25V18a2.25 2.25 0 0 1-2.25 2.25H6A2.25 2.25 0 0 1 3.75 18v-2.25ZM13.5 6a2.25 2.25 0 0 1 2.25-2.25H18A2.25 2.25 0 0 1 20.25 6v2.25A2.25 2.25 0 0 1 18 10.5h-2.25a2.25 2.25 0 0 1-2.25-2.25V6ZM13.5 15.75a2.25 2.25 0 0 1 2.25-2.25H18a2.25 2.25 0 0 1 2.25 2.25V18A2.25 2.25 0 0 1 18 20.25h-2.25a2.25 2.25 0 0 1-2.25-2.25v-2.25Z" />
      </svg>
    ),
  },
  {
    value: "compact",
    label: "Compact",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 0 1 6 3.75h1.5A2.25 2.25 0 0 1 9.75 6v1.5A2.25 2.25 0 0 1 7.5 9.75H6A2.25 2.25 0 0 1 3.75 7.5V6ZM3.75 15A2.25 2.25 0 0 1 6 12.75h1.5A2.25 2.25 0 0 1 9.75 15v1.5A2.25 2.25 0 0 1 7.5 18.75H6A2.25 2.25 0 0 1 3.75 16.5V15ZM11.25 6a2.25 2.25 0 0 1 2.25-2.25h1.5a2.25 2.25 0 0 1 2.25 2.25v1.5a2.25 2.25 0 0 1-2.25 2.25h-1.5A2.25 2.25 0 0 1 11.25 7.5V6ZM11.25 15a2.25 2.25 0 0 1 2.25-2.25h1.5a2.25 2.25 0 0 1 2.25 2.25v1.5a2.25 2.25 0 0 1-2.25 2.25h-1.5a2.25 2.25 0 0 1-2.25-2.25V15ZM18.75 6a2.25 2.25 0 0 1 2.25-2.25h1.5c.621 0 1.125.504 1.125 1.125V7.5c0 .621-.504 1.125-1.125 1.125h-1.5A2.25 2.25 0 0 1 18.75 7.5V6ZM18.75 15a2.25 2.25 0 0 1 2.25-2.25h1.5c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125h-1.5a2.25 2.25 0 0 1-2.25-2.25V15Z" />
      </svg>
    ),
  },
  {
    value: "list",
    label: "List",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 5.25h16.5m-16.5 4.5h16.5m-16.5 4.5h16.5m-16.5 4.5h16.5" />
      </svg>
    ),
  },
  {
    value: "sources",
    label: "Sources",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 7.5h1.5m-1.5 3h1.5m-7.5 3h7.5m-7.5 3h7.5m3-9h3.375c.621 0 1.125.504 1.125 1.125V18a2.25 2.25 0 0 1-2.25 2.25M16.5 7.5V18a2.25 2.25 0 0 0 2.25 2.25M16.5 7.5V4.875c0-.621-.504-1.125-1.125-1.125H4.125C3.504 3.75 3 4.254 3 4.875V18a2.25 2.25 0 0 0 2.25 2.25h13.5" />
      </svg>
    ),
  },
  {
    value: "timeline",
    label: "Timeline",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
      </svg>
    ),
  },
];

export default function ViewModeToggle({ viewMode }: ViewModeToggleProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathname = usePathname();

  function handleModeChange(mode: ViewMode) {
    const params = new URLSearchParams(searchParams.toString());
    if (mode === "topics") {
      params.delete("view");
    } else {
      params.set("view", mode);
    }
    const query = params.toString();
    router.push(query ? `${pathname}?${query}` : pathname);
  }

  return (
    <div className="inline-flex items-center gap-1 rounded-lg bg-gray-100 dark:bg-gray-800 p-1">
      {MODES.map((mode) => (
        <button
          key={mode.value}
          onClick={() => handleModeChange(mode.value)}
          className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
            viewMode === mode.value
              ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm"
              : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
          }`}
        >
          {mode.icon}
          {mode.label}
        </button>
      ))}
    </div>
  );
}
