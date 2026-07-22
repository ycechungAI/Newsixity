import { useState } from "react";

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

  async function markAllRead() {
    if (marking || unreadCount === 0) return;
    setMarking(true);
    try {
      const res = await fetch("/api/articles/mark-all-read", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ categorySlug: categorySlug ?? null }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.marked > 0) {
          window.dispatchEvent(new CustomEvent("feeds-refreshed"));
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
