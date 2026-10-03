import { useState, useEffect } from "react";
import FeedManager from "@/components/settings/FeedManager";
import FeedRankings from "@/components/settings/FeedRankings";
import RankingSettingsPanel from "@/components/settings/RankingSettingsPanel";
import SearchLinksManager from "@/components/settings/SearchLinksManager";

interface OllamaModel   { name: string; size: string | number; modified?: string }
interface SuggestedModel { name: string; size: string; description: string; recommended: boolean; installed: boolean }

export default function SettingsPage() {
  const [apiKey,      setApiKey]      = useState("");
  const [ollamaModel, setOllamaModel] = useState("llama3.2");
  const [ollamaHost,  setOllamaHost]  = useState("http://localhost:11434");

  const [installedModels,  setInstalledModels]  = useState<OllamaModel[]>([]);
  const [suggestedModels,  setSuggestedModels]  = useState<SuggestedModel[]>([]);
  const [ollamaRunning,    setOllamaRunning]    = useState(false);

  // Which sections have ranking switched on (§4.2: Feed Rankings has to be
  // able to say "this weight is stored but does nothing" rather than imply
  // every category is ranked).
  const [rankedSlugs, setRankedSlugs] = useState<Set<string>>(new Set());

  const [loading, setLoading] = useState(false);
  const [saving,  setSaving]  = useState(false);
  const [msg,     setMsg]     = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => { loadSettings(); loadOllamaModels(); loadRankedCategories(); }, []);

  async function loadRankedCategories() {
    const res = await fetch("/api/ranking/settings");
    if (!res.ok) return;
    const data = await res.json();
    const slugs = (data.settings || [])
      .filter((s: { ranked: boolean }) => s.ranked)
      .map((s: { categorySlug: string }) => s.categorySlug);
    setRankedSlugs(new Set(slugs));
  }

  async function loadSettings() {
    const res = await fetch("/api/settings");
    if (res.ok) {
      const { settings } = await res.json();
      setApiKey(settings.brave_search_api_key || "");
      setOllamaModel(settings.ollama_model || "llama3.2");
      setOllamaHost(settings.ollama_host || "http://localhost:11434");
    }
  }

  async function loadOllamaModels() {
    setLoading(true);
    try {
      const res = await fetch("/api/ollama/models");
      if (res.ok) {
        const data = await res.json();
        setOllamaRunning(data.isRunning);
        setInstalledModels(data.installed || []);
        setSuggestedModels(data.suggestions || []);
      }
    } finally { setLoading(false); }
  }

  async function save() {
    setSaving(true); setMsg(null);
    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ brave_search_api_key: apiKey, ollama_model: ollamaModel, ollama_host: ollamaHost }),
      });
      if (res.ok) {
        setMsg({ ok: true, text: "Settings saved." });
        await loadSettings();
      } else {
        const d = await res.json();
        setMsg({ ok: false, text: d.error || "Failed to save." });
      }
    } catch { setMsg({ ok: false, text: "Network error." }); }
    finally { setSaving(false); }
  }

  return (
    <div className="settings-page page">
      <h1>Settings</h1>

      {msg && <div className={`settings-msg ${msg.ok ? "ok" : "err"}`}>{msg.text}</div>}

      {/* Brave Search API Key */}
      <div className="settings-section">
        <div className="settings-section-head">
          <div className="settings-section-title">Brave Search API Key</div>
          <div className="settings-section-sub">
            Required for Deep Research. Get a free key at{" "}
            <a href="https://brave.com/search/api/" target="_blank" rel="noopener noreferrer">
              brave.com/search/api
            </a>
          </div>
        </div>
        <div className="settings-body">
          <div className="settings-row">
            <label>API Key</label>
            <input
              type="password"
              className="settings-input"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder="Paste your key here"
            />
          </div>
          <div style={{ fontSize: 10, color: "var(--subtle)" }}>🔒 Stored securely, cannot be viewed once saved.</div>
        </div>
      </div>

      {/* Ollama */}
      <div className="settings-section">
        <div className="settings-section-head">
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span className="settings-section-title">Ollama Configuration</span>
            <span className="ollama-status">
              <span className={ollamaRunning ? "dot-green" : "dot-red"} />
              {ollamaRunning ? "Running" : "Offline"}
            </span>
          </div>
          <div className="settings-section-sub">AI summarization & research</div>
        </div>
        <div className="settings-body">
          <div className="settings-row">
            <label>Host</label>
            <input
              type="text"
              className="settings-input"
              value={ollamaHost}
              onChange={e => setOllamaHost(e.target.value)}
              placeholder="http://localhost:11434"
            />
          </div>

          {ollamaRunning && installedModels.length > 0 && (
            <div className="settings-row">
              <label>Model</label>
              <select className="settings-select" value={ollamaModel} onChange={e => setOllamaModel(e.target.value)}>
                {installedModels.map(m => (
                  <option key={m.name} value={m.name}>
                    {m.name} ({typeof m.size === "number" ? `${(m.size / 1e9).toFixed(1)}GB` : m.size})
                  </option>
                ))}
              </select>
            </div>
          )}

          {!ollamaRunning && (
            <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 6 }}>
              Ollama is optional. News, saved links, and videos work without it; start Ollama only to enable AI summaries and research.
            </div>
          )}

          <button
            className="tb-btn"
            onClick={loadOllamaModels}
            disabled={loading}
            style={{ marginBottom: 8 }}
          >
            {loading ? "Refreshing…" : "↺ Refresh Ollama"}
          </button>

          {suggestedModels.length > 0 && (
            <>
              <div style={{ fontSize: 10, fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: ".05em", marginBottom: 4 }}>
                Suggested Models
              </div>
              <ul className="model-list">
                {suggestedModels.map(m => (
                  <li key={m.name} className="model-item">
                    <span>
                      <span className="model-name">{m.name}</span>
                      {" "}
                      {m.recommended && <span className="model-tag model-tag-blue">Recommended</span>}
                      {m.installed   && <span className="model-tag model-tag-green">✓ Installed</span>}
                      <br />
                      <span style={{ fontSize: 10, color: "var(--subtle)" }}>{m.description} · {m.size}</span>
                    </span>
                    {!m.installed && (
                      <span className="model-pull"><code>ollama pull {m.name}</code></span>
                    )}
                  </li>
                ))}
              </ul>
              <div style={{ fontSize: 10, color: "var(--subtle)", marginTop: 4 }}>
                Run the command in your terminal to download a model.
              </div>
            </>
          )}
        </div>
      </div>

      <FeedManager />

      <SearchLinksManager />

      <FeedRankings rankedSlugs={rankedSlugs} />

      <RankingSettingsPanel onSaved={() => void loadRankedCategories()} />

      {/* Save */}
      <button className="settings-save-btn" onClick={save} disabled={saving}>
        {saving ? "Saving…" : "Save Settings"}
      </button>
    </div>
  );
}
