"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

interface OllamaModel {
  name: string;
  size: string | number;
  modified?: string;
}

interface SuggestedModel {
  name: string;
  size: string;
  description: string;
  recommended: boolean;
  installed: boolean;
}

export default function SettingsPage() {
  const [apiKey, setApiKey] = useState("");
  const [ollamaModel, setOllamaModel] = useState("llama3.2");
  const [ollamaHost, setOllamaHost] = useState("http://localhost:11434");

  const [installedModels, setInstalledModels] = useState<OllamaModel[]>([]);
  const [suggestedModels, setSuggestedModels] = useState<SuggestedModel[]>([]);
  const [ollamaRunning, setOllamaRunning] = useState(false);

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Load settings
  useEffect(() => {
    loadSettings();
    loadOllamaModels();
  }, []);

  const loadSettings = async () => {
    try {
      const res = await fetch("/api/settings");
      if (res.ok) {
        const data = await res.json();
        setApiKey(data.settings.brave_search_api_key || "");
        setOllamaModel(data.settings.ollama_model || "llama3.2");
        setOllamaHost(data.settings.ollama_host || "http://localhost:11434");
      }
    } catch (e) {
      console.error("Failed to load settings:", e);
    }
  };

  const loadOllamaModels = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/ollama/models");
      if (res.ok) {
        const data = await res.json();
        setOllamaRunning(data.isRunning);
        setInstalledModels(data.installed || []);
        setSuggestedModels(data.suggestions || []);
      }
    } catch (e) {
      console.error("Failed to load Ollama models:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);

    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          brave_search_api_key: apiKey,
          ollama_model: ollamaModel,
          ollama_host: ollamaHost,
        }),
      });

      if (res.ok) {
        setMessage({ type: "success", text: "Settings saved successfully!" });
        // Reload to get masked key
        await loadSettings();
      } else {
        const data = await res.json();
        setMessage({ type: "error", text: data.error || "Failed to save settings" });
      }
    } catch (e) {
      setMessage({ type: "error", text: "Network error. Please try again." });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-white dark:bg-gray-950">
      {/* Header */}
      <header className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center gap-4">
          <Link
            href="/"
            className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
          </Link>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Settings</h1>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8 space-y-8">
        {/* Success/Error Message */}
        {message && (
          <div
            className={`p-4 rounded-lg border ${
              message.type === "success"
                ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border-green-200 dark:border-green-800"
                : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border-red-200 dark:border-red-800"
            }`}
          >
            {message.text}
          </div>
        )}

        {/* Brave Search API Key */}
        <section className="bg-gray-50 dark:bg-gray-900 rounded-xl p-6 border border-gray-200 dark:border-gray-800">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
            Brave Search API Key
          </h2>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Required for Deep Research feature. Get your free API key at{" "}
            <a
              href="https://brave.com/search/api/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sky-600 dark:text-sky-400 hover:underline"
            >
              brave.com/search/api
            </a>
          </p>

          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Paste your API key here"
            className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
            🔒 Once saved, the key is stored securely and cannot be viewed or copied
          </p>
        </section>

        {/* Ollama Configuration */}
        <section className="bg-gray-50 dark:bg-gray-900 rounded-xl p-6 border border-gray-200 dark:border-gray-800">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Ollama Configuration
              </h2>
              <div className="flex items-center gap-2 mt-1">
                <div
                  className={`w-2 h-2 rounded-full ${
                    ollamaRunning ? "bg-green-500" : "bg-red-500"
                  }`}
                />
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  {ollamaRunning ? "Ollama is running" : "Ollama is offline"}
                </span>
              </div>
            </div>
            <button
              onClick={loadOllamaModels}
              disabled={loading}
              className="px-3 py-1.5 text-sm font-medium rounded-lg bg-gray-200 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-700 disabled:opacity-50 transition-colors"
            >
              {loading ? "Refreshing..." : "Refresh"}
            </button>
          </div>

          {/* Host */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Ollama Host
            </label>
            <input
              type="text"
              value={ollamaHost}
              onChange={(e) => setOllamaHost(e.target.value)}
              placeholder="http://localhost:11434"
              className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>

          {/* Model Selection */}
          {ollamaRunning && installedModels.length > 0 ? (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Selected Model
              </label>
              <select
                value={ollamaModel}
                onChange={(e) => setOllamaModel(e.target.value)}
                className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-sky-500"
              >
                {installedModels.map((model) => (
                  <option key={model.name} value={model.name}>
                    {model.name}{" "}
                    {typeof model.size === "number"
                      ? `(${(model.size / 1e9).toFixed(1)}GB)`
                      : `(${model.size})`}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div className="text-sm text-gray-600 dark:text-gray-400">
              {ollamaRunning
                ? "No models installed yet. See suggestions below."
                : "Start Ollama to see installed models."}
            </div>
          )}

          {/* Suggested Models */}
          {suggestedModels.length > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                Suggested Models
              </h3>
              <div className="space-y-2">
                {suggestedModels.map((model) => (
                  <div
                    key={model.name}
                    className={`p-3 rounded-lg border ${
                      model.installed
                        ? "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800"
                        : "bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700"
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-gray-900 dark:text-gray-100">
                            {model.name}
                          </span>
                          {model.recommended && (
                            <span className="text-xs px-2 py-0.5 rounded bg-sky-100 dark:bg-sky-900/30 text-sky-700 dark:text-sky-400">
                              Recommended
                            </span>
                          )}
                          {model.installed && (
                            <span className="text-xs px-2 py-0.5 rounded bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400">
                              ✓ Installed
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                          {model.description} • {model.size}
                        </p>
                      </div>
                      {!model.installed && (
                        <code className="text-xs bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded text-gray-700 dark:text-gray-300">
                          ollama pull {model.name}
                        </code>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-3">
                💡 Run the command in your terminal to download a model
              </p>
            </div>
          )}
        </section>

        {/* Save Button */}
        <div className="flex justify-end">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-2.5 font-medium rounded-lg bg-sky-500 text-white hover:bg-sky-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {saving ? "Saving..." : "Save Settings"}
          </button>
        </div>
      </main>
    </div>
  );
}
