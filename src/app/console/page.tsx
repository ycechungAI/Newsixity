"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

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
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [queueCount, setQueueCount] = useState(0);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [stopping, setStopping] = useState(false);

  useEffect(() => {
    loadData();
    // Refresh every 5 seconds
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const res = await fetch("/api/console");
      if (res.ok) {
        const data = await res.json();
        setQueue(data.queue || []);
        setQueueCount(data.queueCount || 0);
        setLogs(data.logs || []);
      }
    } catch (e) {
      console.error("Failed to load console data:", e);
    } finally {
      setLoading(false);
    }
  };

  const stopServers = async () => {
    if (!confirm("Stop Ollama and Next.js dev servers?")) {
      return;
    }

    setStopping(true);
    try {
      const res = await fetch("/api/console/stop", { method: "POST" });
      if (res.ok) {
        alert("Servers stopped successfully");
      }
    } catch (e) {
      console.error("Failed to stop servers:", e);
      alert("Failed to stop servers");
    } finally {
      setStopping(false);
    }
  };

  return (
    <div className="min-h-screen bg-black">
      {/* Header */}
      <header className="border-b border-green-900/30 bg-black">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center gap-4">
          <Link
            href="/"
            className="text-green-500 hover:text-green-400"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
          </Link>
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <h1 className="text-xl font-semibold text-green-400 font-mono">Console</h1>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={stopServers}
              disabled={stopping}
              className="px-3 py-1.5 text-sm font-medium font-mono rounded-lg bg-red-900/30 text-red-400 hover:bg-red-900/50 border border-red-700/50 transition-colors disabled:opacity-50"
            >
              {stopping ? "Stopping..." : "STOP"}
            </button>
            <button
              onClick={loadData}
              className="px-3 py-1.5 text-sm font-medium font-mono rounded-lg bg-green-900/30 text-green-400 hover:bg-green-900/50 border border-green-700/50 transition-colors"
            >
              Refresh
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8 space-y-6">
        {/* Summarization Queue */}
        <section className="bg-black rounded-xl p-6 border border-green-900/30">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-semibold text-green-400 font-mono">
                Summarization Queue
              </h2>
              <p className="text-sm text-green-500 font-mono mt-1">
                {queueCount > 0 ? (
                  <>
                    {queueCount} article{queueCount !== 1 ? "s" : ""} pending summarization
                    {queue.length < queueCount && ` (showing next ${queue.length})`}
                  </>
                ) : (
                  "No articles pending summarization"
                )}
              </p>
            </div>
            {queueCount > 0 && (
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                <span className="text-sm text-green-500 font-mono">Processing</span>
              </div>
            )}
          </div>

          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 bg-green-900/20 rounded-lg animate-pulse border border-green-900/30" />
              ))}
            </div>
          ) : queue.length > 0 ? (
            <div className="space-y-2">
              {queue.map((item, index) => (
                <div
                  key={item.id}
                  className="p-3 bg-green-950/30 rounded-lg border border-green-900/30"
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-green-900/50 text-green-400 flex items-center justify-center text-sm font-medium font-mono">
                      {index + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-medium text-green-300 truncate font-mono">
                        {item.title}
                      </h3>
                      <div className="flex items-center gap-3 mt-1 text-xs text-green-500 font-mono">
                        <span className="flex items-center gap-1">
                          <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                            item.categorySlug === 'world-news' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400' :
                            item.categorySlug === 'technology' ? 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400' :
                            item.categorySlug === 'finance' ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' :
                            item.categorySlug === 'sports' ? 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400' :
                            'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-400'
                          }`}>
                            {item.categorySlug}
                          </span>
                        </span>
                        <span>•</span>
                        <span>{item.feedName}</span>
                        <span>•</span>
                        <span>{new Date(item.fetchedAt).toLocaleString()}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <svg
                className="w-16 h-16 mx-auto mb-4 text-green-500"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <h3 className="text-lg font-medium text-green-400 mb-1 font-mono">
                All Caught Up!
              </h3>
              <p className="text-sm text-green-500 font-mono">
                No articles pending summarization
              </p>
            </div>
          )}
        </section>

        {/* Debug Logs */}
        <section className="bg-black rounded-xl p-6 border border-green-900/30">
          <h2 className="text-lg font-semibold text-green-400 mb-4 font-mono">
            System Logs
          </h2>

          {logs.length > 0 ? (
            <div className="bg-black rounded-lg p-4 font-mono text-sm space-y-1 max-h-96 overflow-y-auto border border-green-900/50">
              {logs.map((log, index) => (
                <div key={index} className="flex items-start gap-2">
                  <span className="text-green-500 flex-shrink-0">
                    [{log.timestamp}]
                  </span>
                  <span className={`flex-shrink-0 font-semibold ${
                    log.level === "error" ? "text-red-500" :
                    log.level === "warn" ? "text-yellow-500" :
                    "text-green-400"
                  }`}>
                    {log.level.toUpperCase()}
                  </span>
                  <span className="text-green-300 break-all">{log.message}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-black rounded-lg p-8 border border-green-900/50">
              <div className="text-center text-green-500 font-mono text-sm">
                No recent log entries
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
