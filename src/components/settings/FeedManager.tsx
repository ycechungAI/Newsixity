import { useEffect, useState } from "react";
import { apiErrorMessage } from "@/lib/utils/apiError";
import { confirmDialog } from "@/lib/ui/dialog";

interface Feed {
  id: number;
  name: string;
  url: string;
  enabled: boolean;
  categorySlug: string | null;
  lastFetchedAt: string | null;
  lastError: string | null;
}

interface CategoryOption {
  slug: string;
  name: string;
}

// Weather is a dashboard and Top News is promoted from the other
// categories — neither takes feeds of its own.
const NON_FEED_CATEGORIES = new Set(["weather", "top-news"]);
const MANUAL_FEED_URL = "internal://manual";

/** Settings > Feeds: add, rename, disable, move, and delete RSS/Atom feeds. */
export default function FeedManager() {
  const [feeds, setFeeds] = useState<Feed[]>([]);
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  const [open, setOpen] = useState(false);

  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [adding, setAdding] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [editing, setEditing] = useState<{ id: number; name: string } | null>(null);

  useEffect(() => {
    void loadFeeds();
    fetch("/api/categories")
      .then((r) => (r.ok ? r.json() : []))
      .then((cats: CategoryOption[]) => {
        const usable = cats.filter((c) => !NON_FEED_CATEGORIES.has(c.slug));
        setCategories(usable);
        setCategory((prev) => prev || usable[0]?.slug || "");
      })
      .catch(() => {});
  }, []);

  async function loadFeeds() {
    const res = await fetch("/api/feeds");
    if (res.ok) {
      const all: Feed[] = await res.json();
      setFeeds(all.filter((f) => f.url !== MANUAL_FEED_URL));
    }
  }

  async function addFeed(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim() || !category) return;
    setAdding(true);
    setMsg(null);
    try {
      const res = await fetch("/api/feeds", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: url.trim(),
          name: name.trim() || null,
          categorySlug: category,
        }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setMsg({ ok: false, text: apiErrorMessage(data, "Could not add that feed.") });
        return;
      }
      setMsg({ ok: true, text: `Added "${data.name}". Its articles arrive with the next refresh.` });
      setUrl("");
      setName("");
      await loadFeeds();
    } catch {
      setMsg({ ok: false, text: "Could not reach the Newsixity backend." });
    } finally {
      setAdding(false);
    }
  }

  async function patchFeed(id: number, changes: Partial<Pick<Feed, "name" | "enabled" | "categorySlug">>) {
    setMsg(null);
    const res = await fetch(`/api/feeds/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      setMsg({ ok: false, text: apiErrorMessage(data, "Could not update the feed.") });
      return;
    }
    setFeeds((prev) => prev.map((f) => (f.id === id ? { ...f, ...data } : f)));
  }

  async function deleteFeed(feed: Feed) {
    const ok = await confirmDialog(
      `Delete "${feed.name}"? Its unread and read articles are removed. Saved articles are kept under Manual Links.`,
      { confirmLabel: "Delete", danger: true }
    );
    if (!ok) return;
    setMsg(null);
    const res = await fetch(`/api/feeds/${feed.id}`, { method: "DELETE" });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      setMsg({ ok: false, text: apiErrorMessage(data, "Could not delete the feed.") });
      return;
    }
    setFeeds((prev) => prev.filter((f) => f.id !== feed.id));
    const kept = data?.keptSavedArticles ?? 0;
    setMsg({
      ok: true,
      text: `Deleted "${feed.name}"${kept ? ` — ${kept} saved article${kept === 1 ? "" : "s"} kept under Manual Links` : ""}.`,
    });
  }

  async function saveRename() {
    if (!editing) return;
    const trimmed = editing.name.trim();
    const current = feeds.find((f) => f.id === editing.id);
    if (trimmed && current && trimmed !== current.name) {
      await patchFeed(editing.id, { name: trimmed });
    }
    setEditing(null);
  }

  return (
    <div className="settings-section">
      <div className="settings-section-head">
        <div className="settings-section-title">Feeds</div>
        <div className="settings-section-sub">Add your own RSS/Atom feeds, or turn existing ones off</div>
      </div>
      <div className="settings-body">
        {msg && <div className={`settings-msg ${msg.ok ? "ok" : "err"}`}>{msg.text}</div>}

        <form className="feed-add-form" onSubmit={addFeed}>
          <input
            type="url"
            className="settings-input"
            placeholder="https://example.com/feed.xml"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            aria-label="Feed URL"
            required
          />
          <input
            type="text"
            className="settings-input"
            placeholder="Name (optional)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            aria-label="Feed name"
            maxLength={120}
          />
          <select
            className="feed-select"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            aria-label="Feed category"
          >
            {categories.map((c) => (
              <option key={c.slug} value={c.slug}>{c.name}</option>
            ))}
          </select>
          <button type="submit" className="tb-btn" disabled={adding || !url.trim()}>
            {adding ? "Checking…" : "Add feed"}
          </button>
        </form>

        <button className="tb-btn" onClick={() => setOpen((o) => !o)} style={{ margin: "6px 0" }}>
          {open ? "▲ Hide feeds" : `▼ Show all ${feeds.length} feeds`}
        </button>

        {open && (
          <div className="feed-manage-list">
            {feeds.map((f) => (
              <div key={f.id} className={`feed-row${f.enabled ? "" : " is-disabled"}`}>
                <input
                  type="checkbox"
                  checked={f.enabled}
                  onChange={(e) => void patchFeed(f.id, { enabled: e.target.checked })}
                  title={f.enabled ? "Enabled — uncheck to stop fetching" : "Disabled"}
                  aria-label={`Enable ${f.name}`}
                />
                {editing?.id === f.id ? (
                  <input
                    className="settings-input"
                    value={editing.name}
                    autoFocus
                    maxLength={120}
                    onChange={(e) => setEditing({ id: f.id, name: e.target.value })}
                    onBlur={() => void saveRename()}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") void saveRename();
                      if (e.key === "Escape") setEditing(null);
                    }}
                    aria-label="Feed name"
                  />
                ) : (
                  <span className="feed-name" title={f.lastError ? `${f.url}\nLast error: ${f.lastError}` : f.url}>
                    {f.name}
                    {f.lastError && <span className="feed-error"> ⚠ {f.lastError}</span>}
                  </span>
                )}
                <select
                  className="feed-select"
                  value={f.categorySlug ?? ""}
                  onChange={(e) => void patchFeed(f.id, { categorySlug: e.target.value })}
                  aria-label={`Category for ${f.name}`}
                >
                  {categories.map((c) => (
                    <option key={c.slug} value={c.slug}>{c.name}</option>
                  ))}
                </select>
                <button
                  className="act-btn"
                  onClick={() => setEditing({ id: f.id, name: f.name })}
                  title="Rename"
                >
                  Rename
                </button>
                <button className="act-btn" onClick={() => void deleteFeed(f)} title="Delete feed">
                  Delete
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
