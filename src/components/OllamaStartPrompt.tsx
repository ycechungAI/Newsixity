import { useEffect, useState } from "react";
import Modal from "@/components/ui/Modal";

const DISMISSED_KEY = "newsixity-ollama-start-prompt-dismissed";

/**
 * Startup prompt: if the Ollama binary is installed on this computer but the
 * server isn't running, ask the user whether they want to start it (AI
 * summaries stay off until it runs). Article fetching never depends on
 * Ollama — this prompt only gates the optional summarization features.
 *
 * "Not now" dismisses for this session; "Don't ask again" persists in
 * localStorage (per machine, so a DB moved to another computer re-asks).
 */
export default function OllamaStartPrompt() {
  const [open, setOpen] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dontAskAgain, setDontAskAgain] = useState(false);

  useEffect(() => {
    if (localStorage.getItem(DISMISSED_KEY) === "1") return;
    let cancelled = false;
    fetch("/api/ollama/models")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        // Installed on disk but the server isn't reachable → ask.
        if (data.binaryInstalled && !data.isRunning) setOpen(true);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  function dismiss(persist: boolean) {
    if (persist) localStorage.setItem(DISMISSED_KEY, "1");
    setOpen(false);
    setError(null);
    setDontAskAgain(false);
  }

  async function startOllama() {
    setStarting(true);
    setError(null);
    try {
      const res = await fetch("/api/ollama/start", { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.success) {
        // Started (or was already running) — don't ask again on next launch.
        localStorage.setItem(DISMISSED_KEY, "1");
        setOpen(false);
      } else {
        setError(data.detail || data.message || "Could not start Ollama.");
      }
    } catch {
      setError("Could not reach the Newsixity backend.");
    } finally {
      setStarting(false);
    }
  }

  return (
    <Modal isOpen={open} onClose={() => dismiss(dontAskAgain)} title="Ollama is installed but not running">
      <p style={{ fontSize: 13, lineHeight: 1.5, margin: "0 0 12px" }}>
        Newsixity pulls news articles with or without Ollama. But AI article
        summaries need it running. Start it now?
      </p>
      {error && (
        <p style={{ fontSize: 13, color: "var(--danger)", margin: "0 0 12px" }}>{error}</p>
      )}
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, margin: "0 0 16px", cursor: "pointer" }}>
        <input
          type="checkbox"
          checked={dontAskAgain}
          onChange={(e) => setDontAskAgain(e.target.checked)}
        />
        Don&apos;t ask me again
      </label>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <button
          className="app-dialog-btn"
          onClick={() => dismiss(dontAskAgain)}
          disabled={starting}
          style={{ cursor: "pointer" }}
        >
          Not now
        </button>
        <button
          className="app-dialog-btn is-primary"
          onClick={startOllama}
          disabled={starting}
          style={{ cursor: "pointer" }}
        >
          {starting ? "Starting Ollama…" : "Start Ollama"}
        </button>
      </div>
    </Modal>
  );
}
