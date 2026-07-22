import { useState } from "react";

export function RefreshButton() {
  const [busy, setBusy] = useState(false);

  async function refresh() {
    setBusy(true);
    try {
      await fetch("/api/feeds/refresh", { method: "POST" });
      window.dispatchEvent(new CustomEvent("feeds-refreshed"));
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
