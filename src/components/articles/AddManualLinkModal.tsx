"use client";

import { useState } from "react";
import Modal from "@/components/ui/Modal";

interface AddManualLinkModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export default function AddManualLinkModal({ isOpen, onClose, onSuccess }: AddManualLinkModalProps) {
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/articles/manual", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, title, content: content || undefined }),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || "Failed to add link");
      }
      setUrl(""); setTitle(""); setContent("");
      onClose();
      onSuccess?.();
      window.location.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setUrl(""); setTitle(""); setContent(""); setError(null);
    onClose();
  };

  const row: React.CSSProperties = { marginBottom: 10 };
  const label: React.CSSProperties = { display: "block", fontSize: 10, color: "var(--muted)", marginBottom: 3 };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Add External Link">
      <form onSubmit={handleSubmit}>
        {error && (
          <div className="settings-msg err" style={{ marginBottom: 10 }}>{error}</div>
        )}

        <div style={row}>
          <label style={label}>URL *</label>
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/article"
            required
            className="settings-input"
            style={{ width: "100%" }}
          />
        </div>

        <div style={row}>
          <label style={label}>Title *</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Article title"
            required
            maxLength={500}
            className="settings-input"
            style={{ width: "100%" }}
          />
        </div>

        <div style={row}>
          <label style={label}>Description (optional)</label>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Brief description or notes"
            rows={3}
            className="settings-input"
            style={{ width: "100%", resize: "vertical" }}
          />
        </div>

        <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
          <button type="button" onClick={handleClose} className="tb-btn" style={{ flex: 1 }}>Cancel</button>
          <button
            type="submit"
            disabled={loading || !url || !title}
            className="settings-save-btn"
            style={{ flex: 1 }}
          >
            {loading ? "Adding…" : "Add Link"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
