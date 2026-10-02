import { useEffect, useState } from "react";
import { apiErrorMessage } from "@/lib/utils/apiError";

interface SearchLink {
  name: string;
  template: string;
}

/** Settings > Search links: outbound search templates shown on /search. */
export default function SearchLinksManager() {
  const [links, setLinks] = useState<SearchLink[]>([]);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    fetch("/api/search-links")
      .then((r) => (r.ok ? r.json() : { links: [] }))
      .then((data) => setLinks(data.links ?? []))
      .catch(() => {});
  }, []);

  function edit(i: number, changes: Partial<SearchLink>) {
    setLinks((prev) => prev.map((l, j) => (j === i ? { ...l, ...changes } : l)));
  }

  async function save() {
    setSaving(true);
    setMsg(null);
    // Rows left completely blank are just unused "add" rows, not errors.
    const filled = links.filter((l) => l.name.trim() || l.template.trim());
    try {
      const res = await fetch("/api/search-links", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ links: filled }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setMsg({ ok: false, text: apiErrorMessage(data, "Could not save search links.") });
        return;
      }
      setLinks(data.links);
      setMsg({ ok: true, text: "Search links saved." });
    } catch {
      setMsg({ ok: false, text: "Could not reach the Newsixity backend." });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="settings-section">
      <div className="settings-section-head">
        <div className="settings-section-title">Search Links</div>
        <div className="settings-section-sub">
          Shown on the search page as one-click searches elsewhere. Put <code>{"{q}"}</code> where the search term goes.
        </div>
      </div>
      <div className="settings-body">
        {msg && <div className={`settings-msg ${msg.ok ? "ok" : "err"}`}>{msg.text}</div>}
        {links.map((l, i) => (
          <div key={i} className="settings-row">
            <input
              className="settings-input"
              style={{ maxWidth: 140 }}
              value={l.name}
              maxLength={40}
              placeholder="Name"
              onChange={(e) => edit(i, { name: e.target.value })}
              aria-label={`Search link ${i + 1} name`}
            />
            <input
              className="settings-input"
              value={l.template}
              maxLength={500}
              placeholder="https://example.com/search?q={q}"
              onChange={(e) => edit(i, { template: e.target.value })}
              aria-label={`Search link ${i + 1} URL template`}
            />
            <button
              className="act-btn"
              onClick={() => setLinks((prev) => prev.filter((_, j) => j !== i))}
              title="Remove"
            >
              ×
            </button>
          </div>
        ))}
        <div style={{ display: "flex", gap: 6 }}>
          <button
            className="tb-btn"
            onClick={() => setLinks((prev) => [...prev, { name: "", template: "" }])}
            disabled={links.length >= 20}
          >
            + Add link
          </button>
          <button className="tb-btn" onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save links"}
          </button>
        </div>
      </div>
    </div>
  );
}
