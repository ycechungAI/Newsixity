"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface ReadToggleToolbarProps {
  autoMarkRead: boolean;
  onAutoMarkReadChange: (value: boolean) => void;
  unreadCount: number;
  categorySlug?: string | null;
}

export default function ReadToggleToolbar({
  autoMarkRead,
  onAutoMarkReadChange,
  unreadCount,
  categorySlug,
}: ReadToggleToolbarProps) {
  const [marking, setMarking] = useState(false);
  const router = useRouter();

  async function handleMarkAllRead() {
    if (marking || unreadCount === 0) return;
    setMarking(true);

    try {
      const res = await fetch("/api/articles/mark-all-read", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: categorySlug ?? null }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.marked > 0) {
          window.dispatchEvent(
            new CustomEvent("bulk-mark-read", {
              detail: { categorySlug: categorySlug ?? null, count: data.marked },
            })
          );
          router.refresh();
        }
      }
    } catch {
      // silently fail
    } finally {
      setMarking(false);
    }
  }

  return (
    <div className="flex items-center gap-4 mb-4 px-1">
      <button
        onClick={handleMarkAllRead}
        disabled={marking || unreadCount === 0}
        className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
        </svg>
        {marking ? "Marking..." : `Mark all read (${unreadCount})`}
      </button>

      <label className="inline-flex items-center gap-2 cursor-pointer text-xs text-gray-500 dark:text-gray-400">
        <span>Auto-read</span>
        <button
          role="switch"
          aria-checked={autoMarkRead}
          onClick={() => onAutoMarkReadChange(!autoMarkRead)}
          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
            autoMarkRead ? "bg-sky-500" : "bg-gray-300 dark:bg-gray-600"
          }`}
        >
          <span
            className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
              autoMarkRead ? "translate-x-[18px]" : "translate-x-0.5"
            }`}
          />
        </button>
      </label>
    </div>
  );
}
