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

  async function markAllRead() {
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
          window.dispatchEvent(new CustomEvent("bulk-mark-read", {
            detail: { categorySlug: categorySlug ?? null, count: data.marked },
          }));
          router.refresh();
        }
      }
    } catch { /* silent */ } finally {
      setMarking(false);
    }
  }

  return (
    <div className="toolbar" style={{ marginBottom: 6 }}>
      <button
        className="tb-btn"
        onClick={markAllRead}
        disabled={marking || unreadCount === 0}
      >
        {marking ? "Marking…" : `✓ Mark all read (${unreadCount})`}
      </button>
      <label style={{ fontSize: 11, color: "var(--muted)", display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
        <input
          type="checkbox"
          checked={autoMarkRead}
          onChange={e => onAutoMarkReadChange(e.target.checked)}
          style={{ cursor: "pointer" }}
        />
        Auto-read
      </label>
    </div>
  );
}
