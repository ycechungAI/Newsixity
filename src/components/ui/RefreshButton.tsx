"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function RefreshButton() {
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  async function refresh() {
    setBusy(true);
    try {
      await fetch("/api/feeds/refresh", { method: "POST" });
      router.refresh();
    } catch { /* silent */ } finally {
      setBusy(false);
    }
  }

  return (
    <button className="refresh-btn" onClick={refresh} disabled={busy}>
      {busy ? "Refreshing…" : "↺ Refresh"}
    </button>
  );
}
