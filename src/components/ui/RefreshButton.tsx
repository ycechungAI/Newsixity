import { useState } from "react";
import { apiErrorMessage } from "@/lib/utils/apiError";

interface FeedCap {
  feedId: number;
  feedName: string;
  categorySlug: string;
  /** "soft" | "hard" | null — null means the feed simply had nothing new. */
  limit: "soft" | "hard" | null;
  stored24h: number;
  softCap: number;
  hardCap: number;
}

interface RefreshResult {
  refreshed: number;
  newArticles: number;
  errors: string[];
  caps: FeedCap[];
}

function limitLabel(cap: FeedCap): string {
  if (cap.limit === "hard") return `hit its hard cap of ${cap.hardCap}`;
  if (cap.limit === "soft") {
    return `held at the soft cap of ${cap.softCap} until every feed in ${cap.categorySlug} reached it`;
  }
  return "nothing new";
}

export function RefreshButton() {
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setBusy(true);
    setReport(null);
    setError(null);
    try {
      const res = await fetch("/api/feeds/refresh", { method: "POST" });
      // spec-v0.5 2.8/2.10: this used to discard the body entirely and fire
      // the refresh event regardless of status, so a failed refresh looked
      // exactly like a successful one and a capped feed was indistinguishable
      // from a quiet one.
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setError(apiErrorMessage(data, "Refresh failed."));
        return;
      }
      const result = data as RefreshResult;
      const capped = (result.caps || []).filter((c) => c.limit);
      const parts = [`${result.newArticles} new article${result.newArticles === 1 ? "" : "s"}`];
      if (capped.length > 0) {
        parts.push(
          `${capped.length} feed${capped.length === 1 ? "" : "s"} capped: ` +
            capped.map((c) => `${c.feedName} (${limitLabel(c)})`).join("; ")
        );
      }
      if (result.errors?.length) parts.push(`${result.errors.length} error(s)`);
      setReport(parts.join(" — "));
      window.dispatchEvent(new CustomEvent("feeds-refreshed"));
    } catch {
      setError("Could not reach the Newsixity backend.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="refresh-wrap">
      <button className="refresh-btn" onClick={refresh} disabled={busy}>
        {busy ? "Refreshing…" : "↺ Refresh"}
      </button>
      {report && <span className="refresh-report">{report}</span>}
      {error && <span className="refresh-report is-error">{error}</span>}
    </span>
  );
}