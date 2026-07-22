import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";

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

export default function ConsolePage() {
  const [queue, setQueue]           = useState<QueueItem[]>([]);
  const [queueCount, setQueueCount] = useState(0);
  const [logs, setLogs]             = useState<LogEntry[]>([]);
  const [loading, setLoading]       = useState(true);
  const [stopping, setStopping]     = useState(false);
  const [backing, setBacking]       = useState(false);
  const [resummarizing, setResummarizing] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const logsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadData();
    const t = setInterval(loadData, 2000);
    return () => clearInterval(t);
  }, []);

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
    if (!confirm("Remove this article from the summarization queue?")) return;
    try {
      const res = await fetch(`/api/console/queue?id=${id}`, { method: "DELETE" });
      if (res.ok) {
        setQueue(q => q.filter(item => item.id !== id));
        setQueueCount(c => Math.max(0, c - 1));
      }
    } catch { alert("Failed to remove from queue."); }
  }

  async function handleResummarize() {
    if (!confirm("This will reset all failed and skipped articles and put them back in the summarization queue. Continue?")) return;
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

      alert(`Resummarization complete!\n${resetData.message}\nSummarized: ${sumData.summarized}\nErrors: ${sumData.errors.length}`);
      // Refresh console data to see updated queue count and logs
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      alert(`Failed to trigger resummrization: ${message}`);
    } finally {
      setResummarizing(false);
    }
  }

  async function stopServers() {
    if (!confirm("Stop Ollama and dev servers?")) return;
    setStopping(true);
    try {
      await fetch("/api/console/stop", { method: "POST" });
      alert("Servers stopped.");
    } catch { alert("Failed to stop servers."); }
    finally { setStopping(false); }
  }

  async function backupDatabase() {
    setBacking(true);
    try {
      const res = await fetch("/api/console/backup", { method: "POST" });
      const data = await res.json();
      if (res.ok) alert(`Backup created!\n${data.path}\n${data.size}`);
      else alert(`Backup failed: ${data.error}`);
    } catch { alert("Failed to backup database."); }
    finally { setBacking(false); }
  }

  return (
    <div className="console-page">
      {/* Top bar */}
      <div className="console-bar">
        <Link to="/" className="con-btn con-btn-green" title="Back to feed">←</Link>
        <span className="console-bar-title">⬛ Console</span>
        <span style={{ flex: 1 }} />
        <button className="con-btn con-btn-green" onClick={loadData}>↺ Refresh</button>
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
              queue.map((item, i) => (
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
                <div className="con-backup-card-title">Auto Backup</div>
                <div className="con-backup-list">
                  ● Daily at 3 AM<br />
                  ● On app startup<br />
                  ● Keeps 2 most recent
                </div>
                <div className="con-backup-note">Location: <code>data/backups/</code></div>
              </div>
            </div>

            <details className="con-details" style={{ marginTop: 6 }}>
              <summary>📖 How to restore from backup</summary>
              <pre>{`# Stop the app, then:
cp data/newsixity.db data/newsixity.db.old
cp data/backups/newsixity-YYYY-MM-DD....db data/newsixity.db
# Restart the app`}</pre>
            </details>
          </div>
        </div>

        {/* System Logs */}
        <div className="con-section">
          <div className="con-section-head">
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span className="con-section-title">System Logs</span>
              <span style={{ display: "flex", alignItems: "center", gap: 3, fontSize: 10, color: "#4ade80" }}>
                <span className="con-pulse" /> LIVE
              </span>
            </div>
            <button
              className={`con-btn ${autoScroll ? "con-btn-green" : ""}`}
              style={!autoScroll ? { color: "#555", borderColor: "#333" } : {}}
              onClick={() => setAutoScroll(s => !s)}
            >
              Scroll: {autoScroll ? "ON" : "OFF"}
            </button>
          </div>

          <div ref={logsRef} className="con-log-box">
            {logs.length > 0 ? logs.map((log, i) => (
              <div key={i} className="con-log-row">
                <span className="con-log-ts">[{log.timestamp}]</span>
                <span className={`con-log-lvl con-log-${log.level}`}>{log.level.toUpperCase()}</span>
                <span className="con-log-msg">{log.message}</span>
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
