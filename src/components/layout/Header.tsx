"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";

interface HeaderProps {
  onRefresh: () => void;
  isRefreshing: boolean;
  ollamaStatus?: boolean;
}

const RefreshIcon = ({ spinning }: { spinning: boolean }) => (
  <svg
    className={`w-5 h-5 ${spinning ? "animate-spin" : ""}`}
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={1.5}
  >
    <path d="M4 4v5h5M20 20v-5h-5" />
    <path d="M20.49 9A9 9 0 0 0 5.64 5.64L4 7m16 10l-1.64 1.36A9 9 0 0 1 3.51 15" />
  </svg>
);

const SearchIcon = () => (
  <svg
    className="w-4 h-4 text-gray-400"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={2}
  >
    <circle cx="11" cy="11" r="8" />
    <path d="M21 21l-4.35-4.35" />
  </svg>
);

export default function Header({
  onRefresh,
  isRefreshing,
  ollamaStatus,
}: HeaderProps) {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");

  const handleSearch = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter" && searchQuery.trim()) {
        router.push(`/?search=${encodeURIComponent(searchQuery.trim())}`);
      }
    },
    [searchQuery, router]
  );

  return (
    <header className="sticky top-0 z-20 w-full bg-white border-b border-gray-200 h-14 flex items-center px-6">
      {/* Left spacer */}
      <div className="flex-1" />

      {/* Center: Search */}
      <div className="w-full max-w-md">
        <div className="relative">
          <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none">
            <SearchIcon />
          </div>
          <input
            type="text"
            placeholder="Search articles..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleSearch}
            className="w-full bg-gray-100 rounded-full py-2 pl-10 pr-4 text-sm text-gray-900 placeholder-gray-500 border-none outline-none focus:ring-2 focus:ring-sky-500 focus:bg-white transition-colors"
          />
        </div>
      </div>

      {/* Right: actions */}
      <div className="flex-1 flex items-center justify-end gap-3">
        {/* Refresh button */}
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="p-2 rounded-full hover:bg-gray-100 transition-colors disabled:opacity-50 text-gray-600 hover:text-gray-900"
          title="Refresh feeds"
        >
          <RefreshIcon spinning={isRefreshing} />
        </button>

        {/* Ollama status */}
        {ollamaStatus !== undefined && (
          <div className="relative group">
            <div
              className={`w-2.5 h-2.5 rounded-full ${
                ollamaStatus ? "bg-green-500" : "bg-red-500"
              }`}
            />
            <div className="absolute right-0 top-full mt-2 px-2 py-1 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
              {ollamaStatus ? "Ollama connected" : "Ollama offline"}
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
