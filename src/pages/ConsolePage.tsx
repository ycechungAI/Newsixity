import { useState, useEffect, useRef, useCallback, ReactNode } from "react";
import { Link } from "react-router";
import { confirmDialog, notify } from "@/lib/ui/dialog";

/** How often to ask the backend for backfill progress. */
const POLL_MS = 800;
/**
 * Failed polls before the UI admits it has lost contact. Three is ~2.4s,
 * long enough to ride out one slow response, short enough that a genuinely
 * dead backend doesn't leave the user staring at a frozen bar.
 */
const STALE_POLL_LIMIT = 3;

function isSystemMessage(text: string): boolean {
  // \x1b, not \033: octal escapes are a syntax error under TypeScript's
  // stricter parsing, and both denote the same ESC character.
  // no-control-regex guards against control characters appearing by
  // accident; matching ANSI colour codes requires ESC deliberately.
  // eslint-disable-next-line no-control-regex
  return /\x1b\[(92m|93m|91m)/.test(text);
}

function parseAnsiColors(text: string): ReactNode[] {
  const ansiColorMap: Record<string, string> = {
    "[92m": "#4ade80",  // Light green (success)
    "[93m": "#facc15",  // Yellow (warning/skipped)
    "[91m": "#f87171",  // Light red (error/failed)
    "[0m": "inherit",   // Reset
  };

  const parts: ReactNode[] = [];
  let currentColor = "inherit";
  let currentText = "";
  let i = 0;

  while (i < text.length) {
    let found = false;
    for (const [code, color] of Object.entries(ansiColorMap)) {
      if (text.startsWith(code, i)) {
        if (currentText) {
          parts.push(
            <span key={parts.length} style={{ color: currentColor }}>
              {currentText}
            </span>
          );
          currentText = "";
        }
        currentColor = color;
        i += code.length;
        found = true;
        break;
      }
    }
    if (!found) {
      currentText += text[i];
      i++;
    }
  }

  if (currentText) {
    parts.push(
      <span key={parts.length} style={{ color: currentColor }}>
        {currentText}
      </span>
    );
  }

  return parts.length > 0 ? parts : [text];
}

interface QueueItem {
  id: number;
  title: string;
  feedName: string;
  categorySlug: string;
  publishedAt: string | null;
  fetchedAt: string;
}

interface LogEntry {
  timestamp: string;
  level: "info" | "warn" | "error";
  message: string;
}

interface BackupItem {
  name: string;
  size: number;
  /** Unix seconds. */
  mtime: number;
  /** "auto" | "manual" | "safety" — safety copies are made before a restore. */
  type: string;
}

interface PrunePreview {
  total_articles: number;
  saved_count: number;
  unread_count: number;
  prunable_by_strategy: {
    duplicates: number;
    old_articles: number;
    /** Articles scoring under the chosen threshold — returned by
     *  GET /api/prune/preview but previously missing from this type, which
     *  is why the two usages below were type errors. */
    below_threshold: number;
    total: number;
  };
  preview_ids: number[];
}

export default function ConsolePage() {
  const [queue, setQueue]           = useState<QueueItem[]>([]);
  const [queueCount, setQueueCount] = useState(0);
  const [logs, setLogs]             = useState<LogEntry[]>([]);
  const [loading, setLoading]       = useState(true);
  const [stopping, setStopping]     = useState(false);
  const [backing, setBacking]       = useState(false);
  const [exporting, setExporting]   = useState(false);
  const [importing, setImporting]   = useState(false);
  const [pendingImport, setPendingImport] = useState<File | null>(null);
  const [backups, setBackups]       = useState<BackupItem[]>([]);
  const [backupsLoading, setBackupsLoading] = useState(false);
  /** Name of the backup awaiting a confirm click, if any. */
  const [pendingRestore, setPendingRestore] = useState<string | null>(null);
  const [resummarizing, setResummarizing] = useState(false);
  /** Live progress of the full-text backfill job, or null when idle. */
  const [backfill, setBackfill] = useState<{
    running: boolean; processed: number; repaired: number; total: number;
    /** null while the total is unknown — render an indeterminate bar. */
    percent: number | null; currentFeed: string | null; cancelled: boolean;
    /** Set when the run ended early. Without it an early stop is
     *  indistinguishable from a finished one, and "0 repaired" reads as
     *  "nothing to do" rather than "stopped, nothing more was repairable". */
    stoppedReason?: string | null;
  } | null>(null);
  const [fullTextPending, setFullTextPending] = useState<number | null>(null);
  const [concurrency, setConcurrency] = useState(0);
  const [maxConcurrency, setMaxConcurrency] = useState(8);
  /** Sources measured as refusing to serve article text; excluded from pending. */
  const [blockedFeeds, setBlockedFeeds] = useState<{ id: number; name: string }[]>([]);
  const [pruning, setPruning]       = useState(false);
  const [prunePreview, setPrunePreview] = useState<PrunePreview | null>(null);
  const [pruneLoading, setPruneLoading] = useState(false);
  const [showPruneConfirm, setShowPruneConfirm] = useState(false);
  const [scoreThreshold, setScoreThreshold] = useState(0);
  const [autoScroll, setAutoScroll] = useState(true);
  const [logTab, setLogTab] = useState<"system" | "console">("system");
  const importInputRef = useRef<HTMLInputElement>(null);
  const logsRef = useRef<HTMLDivElement>(null);
  const pruneLoadingRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    loadData();
    const t = setInterval(loadData, 500);  // Update every 500ms for real-time display
    return () => clearInterval(t);
  }, []);

  // Backups change rarely, so load once rather than joining the 500ms poll.
  useEffect(() => { loadBackups(); }, []);

  useEffect(() => {
    if (autoScroll && logsRef.current)
      logsRef.current.scrollTop = logsRef.current.scrollHeight;
  }, [logs, autoScroll]);

  async function loadData() {
    try {
      const res = await fetch("/api/console");
      if (res.ok) {
        const data = await res.json();
        setQueue(data.queue || []);
        setQueueCount(data.queueCount || 0);
        setLogs(data.logs || []);
      }
    } catch { /* silent */ } finally {
      setLoading(false);
    }
  }

  async function handleRemove(id: number) {
    if (!await confirmDialog("Remove this article from the summarization queue?")) return;
    try {
      const res = await fetch(`/api/console/queue?id=${id}`, { method: "DELETE" });
      if (res.ok) {
        setQueue(q => q.filter(item => item.id !== id));
        setQueueCount(c => Math.max(0, c - 1));
      }
    } catch { void notify("Failed to remove from queue."); }
  }

  const loadFullTextStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/console/full-text-status");
      if (res.ok) {
        const d = await res.json();
        setFullTextPending(d.pending ?? 0);
        setBlockedFeeds(d.blockedFeeds ?? []);
      }
    } catch { /* leave the count unknown rather than showing a wrong number */ }

    try {
      const res = await fetch("/api/console/backfill-full-text/status");
      if (res.ok) {
        const d = await res.json();
        setMaxConcurrency(d.maxConcurrency ?? 8);
        // Adopt the detected default once, but let the user override after.
        if (concurrency === 0 && d.suggestedConcurrency) setConcurrency(d.suggestedConcurrency);
        setBackfill(d.running || d.processed > 0 ? d : null);
      }
    } catch { /* progress is best-effort */ }
  }, [concurrency]);

  // Full-text backfill status changes rarely too, and each run is expensive
  // (one outbound page fetch per article), so keep it out of the 500ms poll.
  useEffect(() => { loadFullTextStatus(); }, [loadFullTextStatus]);

  // Poll only while a run is in flight; the 500ms console poll is too coarse
  // for a progress bar and wasteful when idle.
  //
  // Deliberately does NOT depend on `backfill`. An earlier version did, and
  // that broke it: the effect set `backfill`, which changed the dependency,
  // which tore the interval down and built a new one — resetting the timer
  // before it could ever fire. The bar sat frozen while the job ran happily.
  // Reading `running` from a ref keeps the interval stable.
  const backfillRunningRef = useRef(false);
  /** Consecutive failed polls. The job may still be fine; the UI may not be. */
  const [staleAfter, setStaleAfter] = useState(0);
  useEffect(() => { backfillRunningRef.current = !!backfill?.running; }, [backfill?.running]);

  useEffect(() => {
    let misses = 0;
    const t = setInterval(async () => {
      if (!backfillRunningRef.current) {
        misses = 0;
        setStaleAfter(0);
        return;
      }
      try {
        const res = await fetch("/api/console/backfill-full-text/status");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const d = await res.json();
        setBackfill(d);
        misses = 0;
        setStaleAfter(0);
        if (!d.running) {
          backfillRunningRef.current = false;
          void notify(
            (d.stoppedReason
              ? `Full-text backfill stopped: ${d.repaired} of ${d.processed} articles got full text`
              : `Full-text backfill done: ${d.repaired} of ${d.processed} articles got full text`) +
            (d.cancelled ? " (cancelled)" : "")
          );
          await loadFullTextStatus();
        }
      } catch {
        // Say so. A silent catch here is why a frozen progress bar once looked
        // like a working one — the user had no way to tell a dead backend from
        // a stalled UI, and would sit waiting on a job that had finished.
        misses += 1;
        if (misses >= STALE_POLL_LIMIT) setStaleAfter(misses * POLL_MS);
      }
    }, POLL_MS);
    return () => clearInterval(t);
  }, [loadFullTextStatus]);

  /** Start the continuous job. It repairs everything outstanding, not one batch. */
  async function handleBackfillFullText() {
    if (backfill?.running) return;
    if (fullTextPending === 0) return;
    if (!await confirmDialog(
      "Fetch each article's real text from its source?\n\n" +
      "Most publishers block or paywall this, so many articles will keep their " +
      "feed excerpt. The full-text view on the article page works either way. " +
      "This runs in the background and can be cancelled."
    )) return;

    try {
      const res = await fetch(`/api/console/backfill-full-text?concurrency=${concurrency || 0}`, { method: "POST" });
      const d = await res.json().catch(() => ({}));
      if (!res.ok || d.success === false) {
        void notify(`Could not start backfill: ${d.message ?? res.status}`);
        return;
      }
      setBackfill(d);
    } catch {
      void notify("Failed to start the full-text backfill.");
    }
  }

  /** Clear every "can't serve text" mark so those feeds are tried again. */
  async function handleUnblockFeeds() {
    if (!await confirmDialog(
      `Try ${blockedFeeds.length} blocked source${blockedFeeds.length === 1 ? "" : "s"} again?\n\n` +
      "They'll be included in the pending count once more."
    )) return;
    for (const f of blockedFeeds) {
      await fetch(`/api/console/full-text-unblock?feed_id=${f.id}`, { method: "POST" }).catch(() => {});
    }
    await loadFullTextStatus();
    void notify("Unblocked. Those sources will be tried on the next run.");
  }

  /** Ask the run to stop. It ends after the batch in flight. */
  async function handleCancelBackfill() {
    try {
      const res = await fetch("/api/console/backfill-full-text/cancel", { method: "POST" });
      const d = await res.json().catch(() => ({}));
      if (res.ok && d.success) void notify("Stopping after the current batch…");
    } catch {
      void notify("Failed to send the cancel request.");
    }
  }

  async function handleResummarize() {
    if (!await confirmDialog("This will reset all failed and skipped articles and put them back in the summarization queue. Continue?")) return;
    setResummarizing(true);
    try {
      // Step 1: Reset failed and skipped articles
      const resetRes = await fetch("/api/console/resummarize-failed", { method: "POST" });
      if (!resetRes.ok) {
        const resetError = await resetRes.json();
        throw new Error(resetError.error || "Failed to reset articles");
      }
      const resetData = await resetRes.json();

      // Step 2: Trigger the summarization queue to process the reset articles (and any others in the queue)
      const sumRes = await fetch("/api/summarize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      if (!sumRes.ok) {
        const sumError = await sumRes.json();
        throw new Error(sumError.error || "Summarization failed");
      }
      const sumData = await sumRes.json();

      void notify(`Resummarization complete!\n${resetData.message}\nSummarized: ${sumData.summarized}\nErrors: ${sumData.errors.length}`);
      // Refresh console data to see updated queue count and logs
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      void notify(`Failed to trigger resummrization: ${message}`);
    } finally {
      setResummarizing(false);
    }
  }

  async function stopServers() {
    if (!await confirmDialog("Stop Ollama and dev servers?")) return;
    setStopping(true);
    try {
      await fetch("/api/console/stop", { method: "POST" });
      void notify("Servers stopped.");
    } catch { void notify("Failed to stop servers."); }
    finally { setStopping(false); }
  }

  async function backupDatabase() {
    setBacking(true);
    try {
      const res = await fetch("/api/console/backup", { method: "POST" });
      const data = await res.json();
      if (res.ok) void notify(`Backup created!\n${data.path}\n${data.size}`);
      else void notify(`Backup failed: ${data.error}`);
    } catch { void notify("Failed to backup database."); }
    finally { setBacking(false); }
  }

  async function loadBackups() {
    setBackupsLoading(true);
    try {
      const res = await fetch("/api/console/backups");
      const data = await res.json();
      setBackups(res.ok ? (data.backups ?? []) : []);
    } catch { setBackups([]); }
    finally { setBackupsLoading(false); }
  }

  /**
   * Stage a restore. Either from a backup already on this machine (`name`) or
   * from the file the user picked. Both run the same server-side integrity
   * gate; nothing touches the live DB until the next app start.
   */
  async function stageRestore(opts: { name?: string; file?: File }) {
    setImporting(true);
    try {
      const url = opts.name
        ? `/api/console/backups/restore?name=${encodeURIComponent(opts.name)}`
        : "/api/console/backups/restore";
      const res = await fetch(url, {
        method: "POST",
        ...(opts.file
          ? { body: opts.file, headers: { "Content-Type": "application/octet-stream" } }
          : {}),
      });
      const data = await res.json();
      if (res.ok) {
        void notify(data.message ?? "Restore staged — quit and reopen Newsixity to apply.");
        setPendingImport(null);
        setPendingRestore(null);
        loadBackups();
      } else {
        // The integrity gate rejects here — surface exactly why.
        void notify(`Restore rejected: ${data.error ?? res.status}`);
      }
    } catch { void notify("Failed to stage restore."); }
    finally { setImporting(false); }
  }

  async function importDatabase() {
    if (pendingImport) await stageRestore({ file: pendingImport });
  }

  /**
   * Download a snapshot of the live DB, for carrying to another machine.
   *
   * Goes through fetch rather than pointing the browser straight at the URL
   * so a JSON error body still surfaces as a message instead of the browser
   * silently "downloading" the error. The filename comes from the server's
   * Content-Disposition header.
   */
  /**
   * Export the database to a file on disk.
   *
   * Writes server-side rather than downloading a blob. A blob +
   * `<a download>` is silently a no-op in the packaged app's WKWebView, so
   * the button appeared to do nothing once installed — and there is no
   * reliable way to detect that failure from the page. The backend and the
   * filesystem are the same machine for this app, so writing directly is
   * both simpler and works everywhere.
   */
  async function exportDatabase() {
    setExporting(true);
    try {
      const res = await fetch("/api/console/backups/export-to-disk", { method: "POST" });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        void notify(`Export failed: ${data.error ?? res.status}`);
        return;
      }
      const info = await res.json().catch(() => ({}));
      void notify(info.message ?? "Database exported.");
    } catch { void notify("Failed to export database."); }
    finally { setExporting(false); }
  }

  async function loadPrunePreview(threshold: number = 0) {
    setPruneLoading(true);
    try {
      const res = await fetch(`/api/prune/preview?threshold=${threshold}`);
      if (res.ok) {
        const data = await res.json();
        setPrunePreview(data);
      } else {
        void notify("Failed to load pruning preview.");
      }
    } catch { void notify("Failed to load pruning preview."); }
    finally { setPruneLoading(false); }
  }

  function handleThresholdChange(value: number) {
    setScoreThreshold(value);

    // Debounce API calls while user is adjusting slider
    if (pruneLoadingRef.current) {
      clearTimeout(pruneLoadingRef.current);
    }

    pruneLoadingRef.current = setTimeout(() => {
      loadPrunePreview(value);
    }, 300);
  }

  async function executePrune() {
    if (!prunePreview) return;
    setPruning(true);
    try {
      const res = await fetch(`/api/prune?threshold=${scoreThreshold}`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        void notify(`Pruning complete!\nDeleted: ${data.deleted} articles\n\nThe page will refresh to show updated counts.`);
        setShowPruneConfirm(false);
        setPrunePreview(null);
        // Reload page to refresh article counts
        setTimeout(() => window.location.reload(), 1000);
      } else {
        void notify("Failed to execute pruning.");
      }
    } catch { void notify("Failed to execute pruning."); }
    finally { setPruning(false); }
  }

  return (
    <div className="console-page">
      {/* Top bar */}
      <div className="console-bar">
        <Link to="/" className="con-btn con-btn-green" title="Back to feed">←</Link>
        <span className="console-bar-title">⬛ Console</span>
        <span style={{ flex: 1 }} />
        <button className="con-btn con-btn-green" onClick={loadData}>↺ Refresh</button>
        {backfill?.running ? (
          <button className="con-btn con-btn-red" onClick={handleCancelBackfill}>
            Cancel backfill
          </button>
        ) : (
          <button
            className="con-btn con-btn-green"
            onClick={handleBackfillFullText}
            disabled={fullTextPending === 0}
            title={
              fullTextPending === 0
                ? "Every article already has full text"
                : "Fetch each article's real text from its source, so it survives the link going stale"
            }
          >
            {fullTextPending === 0 ? "Full-text backfill ✓" : "Full-text backfill"}
          </button>
        )}
        <button className="con-btn con-btn-green" onClick={handleResummarize} disabled={resummarizing}>
          {resummarizing ? "Resummarizing…" : "Resummarize"}
        </button>
        <button className="con-btn con-btn-blue"  onClick={backupDatabase} disabled={backing}>
          {backing ? "Backing up…" : "Backup DB"}
        </button>
        <button className="con-btn con-btn-red"   onClick={stopServers}   disabled={stopping}>
          {stopping ? "Stopping…" : "Stop"}
        </button>
      </div>

      <div className="console-body">
        {/* Full-text backfill: progress, concurrency, results */}
        {(backfill || (fullTextPending ?? 0) > 0) && (
          <div className="con-section">
            <div className="con-section-head">
              <div>
                <div className="con-section-title">Full-text backfill</div>
                <div className="con-section-sub">
                  {backfill?.running
                    ? `Fetching article text — ${backfill.processed} done`
                    : backfill
                      ? `${backfill.repaired} repaired of ${backfill.processed} checked`
                      : "Fetch each article's real text from its source"}
                </div>
              </div>
            </div>

            {backfill && (
              <>
                {staleAfter > 0 && (
                  <div className="con-progress-warn" role="alert">
                    No response from the backend for{" "}
                    {Math.round(staleAfter / 1000)}s. The job may still be
                    running — these figures may be out of date. Check the Console
                    log, or reload.
                  </div>
                )}
                {/*
                  No percentage. The total counts every article holding a feed
                  excerpt, but most cannot be scraped at all — paywalled or
                  bot-blocked — so "590 → 100%" promised something the run
                  cannot deliver. It repaired 3 in a full pass. An indeterminate
                  bar with two measured numbers underneath is honest; a
                  confident-looking bar was not.
                */}
                <div
                  className={`con-progress${backfill.running ? " is-indeterminate" : " is-done"}`}
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div
                    className="con-progress-fill"
                    style={{
                      width: backfill.running ? undefined : `${Math.min(100, backfill.percent ?? 0)}%`,
                    }}
                  />
                </div>
                <div className="con-progress-meta">
                  <span>{backfill.processed} checked</span>
                  <span>{backfill.repaired} got full text</span>
                  {backfill.currentFeed && <span>{backfill.currentFeed}</span>}
                </div>
                {!backfill.running && backfill.stoppedReason && (
                  <div className="con-progress-note">{backfill.stoppedReason}</div>
                )}
                {!backfill.running && backfill.processed > 0 && backfill.repaired < backfill.processed * 0.1 && (
                  <div className="con-progress-note">
                    Most sources block or paywall automated fetching, so most
                    articles keep their feed excerpt. That&apos;s the publisher&apos;s
                    choice, not a failure here.
                  </div>
                )}
              </>
            )}

            {blockedFeeds.length > 0 && (
              <div className="con-blocked">
                <span>
                  {blockedFeeds.length} source{blockedFeeds.length === 1 ? "" : "s"} won&apos;t
                  serve article text (paywalled or bot-blocked), so they&apos;re
                  excluded from the count: {blockedFeeds.map(f => f.name).join(", ")}
                </span>
                <button
                  className="con-btn con-btn-blue"
                  onClick={handleUnblockFeeds}
                  title="Clear these marks and include them again"
                >
                  Unblock all
                </button>
              </div>
            )}

            {!backfill?.running && (
              <label className="con-slider">
                <span>
                  Fetch {concurrency || 1} at a time
                  <em>more cores fetch faster; fewer is gentler on publishers</em>
                </span>
                <input
                  type="range"
                  min={1}
                  max={maxConcurrency}
                  value={concurrency || 1}
                  onChange={(e) => setConcurrency(Number(e.target.value))}
                />
              </label>
            )}
          </div>
        )}

        {/* Summarization Queue */}
        <div className="con-section">
          <div className="con-section-head">
            <div>
              <div className="con-section-title">Summarization Queue</div>
              <div className="con-section-sub">
                {queueCount > 0
                  ? `${queueCount} pending${queue.length < queueCount ? ` (showing ${queue.length})` : ""}`
                  : "Queue empty"}
              </div>
            </div>
            {queueCount > 0 && (
              <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10, color: "#4ade80" }}>
                <span className="con-pulse" /> Processing
              </span>
            )}
          </div>

          <div className="con-section-body">
            {loading ? (
              <div style={{ color: "#166534", fontSize: 10 }}>Loading…</div>
            ) : queue.length > 0 ? (
              [...queue].reverse().map((item, i) => (
                <div key={item.id} className="con-queue-item" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className="con-queue-num">{i + 1}.</span>
                  <span className="con-queue-title" style={{ flex: 1 }}>{item.title}</span>
                  <span className="con-queue-meta">{item.categorySlug} · {item.feedName}</span>
                  <button
                    onClick={() => handleRemove(item.id)}
                    className="con-btn con-btn-red"
                    style={{ padding: "0 4px", fontSize: 10, lineHeight: 1 }}
                    title="Remove from queue"
                  >
                    ×
                  </button>
                </div>
              ))
            ) : (
              <div style={{ color: "#166534", fontSize: 10, padding: "4px 0" }}>✓ All caught up</div>
            )}
          </div>
        </div>

        {/* Database Backup */}
        <div className="con-section" style={{ borderColor: "#1a2a4a" }}>
          <div className="con-section-head" style={{ borderColor: "#1a2a4a", background: "#060a10" }}>
            <div className="con-section-title" style={{ color: "#60a5fa" }}>Database Backup</div>
          </div>
          <div className="con-section-body">
            <div className="con-backup-grid">
              <div className="con-backup-card">
                <div className="con-backup-card-title">Manual Backup</div>
                <button className="con-btn con-btn-blue" onClick={backupDatabase} disabled={backing}
                  style={{ width: "100%", marginTop: 2 }}>
                  {backing ? "Creating…" : "Create Backup Now"}
                </button>
                <div className="con-backup-note">Keeps 2 most recent</div>
              </div>
              <div className="con-backup-card">
                <div className="con-backup-card-title">Export / Transfer</div>
                <button className="con-btn con-btn-green" onClick={exportDatabase} disabled={exporting}
                  style={{ width: "100%", marginTop: 2 }}>
                  {exporting ? "Exporting…" : "⬇ Export Database"}
                </button>
                <div className="con-backup-note">
                  Downloads the current database as one file — copy it to another
                  computer and restore it there.
                </div>
              </div>
              <div className="con-backup-card">
                <div className="con-backup-card-title">Import / Restore</div>
                <input
                  ref={importInputRef}
                  type="file"
                  accept=".db"
                  style={{ display: "none" }}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    // Reset first: picking the same file twice must still fire
                    // onChange, and it won't if the input still holds it.
                    e.target.value = "";
                    if (file) setPendingImport(file);
                  }}
                />
                {!pendingImport ? (
                  <button
                    className="con-btn con-btn-orange"
                    onClick={() => importInputRef.current?.click()}
                    disabled={importing}
                    style={{ width: "100%", marginTop: 2 }}
                  >
                    ⬆ Import Database…
                  </button>
                ) : (
                  <>
                    <div className="con-backup-note" style={{ margin: "2px 0 4px" }}>
                      Replace everything with <code>{pendingImport.name}</code>{" "}
                      ({Math.round(pendingImport.size / 1024).toLocaleString()} KB)?
                    </div>
                    <div style={{ display: "flex", gap: 4 }}>
                      <button className="con-btn con-btn-red" onClick={importDatabase}
                        disabled={importing} style={{ flex: 1 }}>
                        {importing ? "Checking…" : "Confirm"}
                      </button>
                      <button className="con-btn" onClick={() => setPendingImport(null)}
                        disabled={importing} style={{ flex: 1 }}>
                        Cancel
                      </button>
                    </div>
                  </>
                )}
                <div className="con-backup-note">
                  Checked for integrity before anything is replaced. Applied when
                  you quit and reopen; your current DB is kept as{" "}
                  <code>pre-restore-*.db</code>.
                </div>
              </div>
              <div className="con-backup-card">
                <div className="con-backup-card-title">Auto Backup</div>
                <div className="con-backup-list">
                  ● Daily at 3 AM<br />
                  ● On app startup<br />
                  ● Keeps 2 most recent
                </div>
                <div className="con-backup-note">Location: <code>data/backups/</code></div>
              </div>
            </div>

            {/* Existing backups — selectable, so restoring doesn't require
                knowing filenames or touching a terminal. */}
            <div className="con-backup-list-head">
              <span>Available backups {backups.length > 0 && `(${backups.length})`}</span>
              <button className="con-btn" onClick={loadBackups} disabled={backupsLoading}>
                {backupsLoading ? "…" : "↺"}
              </button>
            </div>
            {backups.length === 0 ? (
              <div className="con-backup-note" style={{ padding: "4px 0" }}>
                {backupsLoading ? "Loading…" : "No backups yet — create one above."}
              </div>
            ) : (
              <table className="con-backup-table">
                <tbody>
                  {backups.map((b) => (
                    <tr key={b.name}>
                      <td className="con-backup-name" title={b.name}>{b.name}</td>
                      <td><span className={`con-badge con-badge-${b.type}`}>{b.type}</span></td>
                      <td>{Math.round(b.size / 1024).toLocaleString()} KB</td>
                      <td>{new Date(b.mtime * 1000).toLocaleString()}</td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        <a
                          className="con-btn"
                          href={`/api/console/backups/download?name=${encodeURIComponent(b.name)}`}
                          download
                        >
                          ⬇
                        </a>{" "}
                        {pendingRestore === b.name ? (
                          <>
                            <button className="con-btn con-btn-red" disabled={importing}
                              onClick={() => stageRestore({ name: b.name })}>
                              {importing ? "…" : "Confirm"}
                            </button>{" "}
                            <button className="con-btn" disabled={importing}
                              onClick={() => setPendingRestore(null)}>Cancel</button>
                          </>
                        ) : (
                          <button className="con-btn con-btn-orange"
                            onClick={() => setPendingRestore(b.name)}>Restore</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            <details className="con-details" style={{ marginTop: 6 }}>
              <summary>📖 Moving your database to another computer</summary>
              <pre>{`1. Here:  click "Export Database" and save the .db file.
2. Copy that file to the other computer.
3. There: upload it to the restore endpoint —

   curl --data-binary @newsixity-export-....db \\
        -H "Content-Type: application/octet-stream" \\
        http://127.0.0.1:8000/api/console/backups/restore

   It is checked for integrity before anything is replaced,
   and only applied when you quit and reopen the app. Your
   previous database is kept as data/backups/pre-restore-*.db.

Or restore a backup already on this machine by name:
   curl -X POST ".../api/console/backups/restore?name=<file>.db"`}</pre>
            </details>
          </div>
        </div>

        {/* Article Pruning */}
        <div className="con-section" style={{ borderColor: "#2a3a4a" }}>
          <div className="con-section-head" style={{ borderColor: "#2a3a4a", background: "#0a0f15" }}>
            <div className="con-section-title" style={{ color: "#f97316" }}>Article Pruning</div>
          </div>
          <div className="con-section-body">
            {!prunePreview ? (
              <div>
                <div className="con-backup-note" style={{ marginBottom: 8 }}>
                  Smart pruning removes duplicates, old content, and low-scoring articles.
                  <strong style={{ color: "#4ade80" }}> Saved articles are NEVER deleted.</strong>
                  <details style={{ marginTop: 6, fontSize: 11, color: "#666" }}>
                    <summary style={{ cursor: "pointer" }}>Scoring strategy & safety (click to expand)</summary>
                    <div style={{ marginTop: 4, paddingLeft: 8 }}>
                      <strong style={{ color: "#999" }}>Safety:</strong><br/>
                      ✓ Saved articles (favorites): Always preserved<br/>
                      ✓ Unread articles: Always preserved<br/>
                      <br/>
                      <strong style={{ color: "#999" }}>Scoring:</strong><br/>
                      • Saved status: +40 pts (bookmarks scored highest)<br/>
                      • Unread status: +30 pts (user hasn't processed yet)<br/>
                      • Promoted/relevance: +15-20 pts (high-quality detected)<br/>
                      • Recency: +5-10 pts (newer articles preferred)<br/>
                      • Feed quality: +0-1 pts (trusted sources)<br/>
                      <br/>Adjust threshold below to control aggressiveness.
                    </div>
                  </details>
                </div>
                <div style={{ marginBottom: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 12 }}>
                    <label>Score Threshold: <strong style={{ color: "#4ade80" }}>{scoreThreshold}</strong> / 100</label>
                    <span style={{ color: "#666", fontSize: 11 }}>Lower = delete more articles</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={scoreThreshold}
                    onChange={(e) => handleThresholdChange(Number(e.target.value))}
                    style={{ width: "100%", cursor: "pointer" }}
                  />
                </div>
                <button
                  className="con-btn con-btn-blue"
                  onClick={() => loadPrunePreview(scoreThreshold)}
                  disabled={pruneLoading}
                  style={{ width: "100%" }}
                >
                  {pruneLoading ? "Loading…" : "Preview Pruning"}
                </button>
              </div>
            ) : (
              <div>
                <div style={{ fontSize: 12, color: "#999", marginBottom: 8 }}>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 8 }}>
                    <div>
                      <strong>Total Articles:</strong> {prunePreview.total_articles.toLocaleString()}
                    </div>
                    <div>
                      <strong>Saved (Protected):</strong> {prunePreview.saved_count.toLocaleString()}
                    </div>
                    <div>
                      <strong>Unread (Protected):</strong> {prunePreview.unread_count.toLocaleString()}
                    </div>
                    <div>
                      <strong style={{ color: "#ef4444" }}>To Delete:</strong> {prunePreview.prunable_by_strategy.total.toLocaleString()}
                    </div>
                  </div>
                  <div style={{ fontSize: 11, color: "#666", marginBottom: 8 }}>
                    <div>• Duplicates: {prunePreview.prunable_by_strategy.duplicates.toLocaleString()}</div>
                    <div>• Old articles (6+ mo): {prunePreview.prunable_by_strategy.old_articles.toLocaleString()}</div>
                    {prunePreview.prunable_by_strategy.below_threshold > 0 && (
                      <div>• Below score threshold ({scoreThreshold}): {prunePreview.prunable_by_strategy.below_threshold.toLocaleString()}</div>
                    )}
                  </div>
                </div>
                <div style={{ fontSize: 11, color: "#666", marginBottom: 8 }}>
                  <label style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4, cursor: "pointer" }}>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={scoreThreshold}
                      onChange={(e) => handleThresholdChange(Number(e.target.value))}
                      style={{ flex: 1, cursor: "pointer" }}
                    />
                    <span style={{ minWidth: 40 }}>{scoreThreshold}</span>
                  </label>
                </div>
                {!showPruneConfirm ? (
                  <div style={{ display: "flex", gap: 4 }}>
                    <button
                      className="con-btn con-btn-green"
                      onClick={() => setShowPruneConfirm(true)}
                      style={{ flex: 1 }}
                    >
                      Confirm Prune
                    </button>
                    <button
                      className="con-btn"
                      onClick={() => setPrunePreview(null)}
                      style={{ flex: 1, color: "#999", borderColor: "#333" }}
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <div>
                    <div style={{ fontSize: 11, color: "#ef4444", marginBottom: 8, lineHeight: 1.4 }}>
                      ⚠️ This will permanently delete {prunePreview.prunable_by_strategy.total.toLocaleString()} articles.
                      Saved and unread articles will be preserved.
                    </div>
                    <div style={{ display: "flex", gap: 4 }}>
                      <button
                        className="con-btn con-btn-red"
                        onClick={executePrune}
                        disabled={pruning}
                        style={{ flex: 1 }}
                      >
                        {pruning ? "Pruning…" : "Execute Prune"}
                      </button>
                      <button
                        className="con-btn"
                        onClick={() => setShowPruneConfirm(false)}
                        style={{ flex: 1, color: "#999", borderColor: "#333" }}
                      >
                        Back
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* System Logs */}
        <div className="con-section">
          <div className="con-section-head">
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span className="con-section-title">Logs</span>
              <span style={{ display: "flex", alignItems: "center", gap: 3, fontSize: 10, color: "#4ade80" }}>
                <span className="con-pulse" /> LIVE
              </span>
            </div>
            <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
              <div style={{ display: "flex", gap: 2 }}>
                <button
                  className={`con-btn ${logTab === "system" ? "con-btn-green" : ""}`}
                  style={logTab !== "system" ? { color: "#555", borderColor: "#333" } : {}}
                  onClick={() => setLogTab("system")}
                  title="Article summarization status"
                >
                  System Messages
                </button>
                <button
                  className={`con-btn ${logTab === "console" ? "con-btn-green" : ""}`}
                  style={logTab !== "console" ? { color: "#555", borderColor: "#333" } : {}}
                  onClick={() => setLogTab("console")}
                  title="General console output"
                >
                  Console
                </button>
              </div>
              <button
                className={`con-btn ${autoScroll ? "con-btn-green" : ""}`}
                style={!autoScroll ? { color: "#555", borderColor: "#333" } : {}}
                onClick={() => setAutoScroll(s => !s)}
              >
                Scroll: {autoScroll ? "ON" : "OFF"}
              </button>
            </div>
          </div>

          <div ref={logsRef} className="con-log-box">
            {logs.length > 0 ? logs
              .filter(log => logTab === "system" ? isSystemMessage(log.message) : !isSystemMessage(log.message))
              .map((log, i) => (
              <div key={i} className="con-log-row">
                <span className="con-log-ts">[{log.timestamp}]</span>
                <span className={`con-log-lvl con-log-${log.level}`}>{log.level.toUpperCase()}</span>
                <span className="con-log-msg">{parseAnsiColors(log.message)}</span>
              </div>
            )) : (
              <div style={{ color: "#166534", fontSize: 10 }}>No recent log entries</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
