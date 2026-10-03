import { useEffect, useMemo, useState } from "react";
import { apiErrorMessage } from "@/lib/utils/apiError";
import {
  DEFAULT_WEIGHT,
  WEIGHT_PRESETS,
  presetValue,
  presetWeight,
} from "@/lib/ranking/weightPresets";

interface Feed {
  id: number;
  name: string;
  enabled: boolean;
  categorySlug?: string | null;
  sourceWeight: number;
}

interface Category {
  slug: string;
  name: string;
}

interface FeedRankingsProps {
  /** Ranked sections, so an unranked group can say so rather than implying
   * its dials do nothing. Fetched from /api/ranking/settings. */
  rankedSlugs: Set<string>;
}

/** Settings › Feed Rankings: a weight per feed, grouped by category.
 *
 * spec-v0.5 §4.1: this used to filter to a hard-coded list of four slugs —
 * the same four as the v0.4 CAPPED_CATEGORIES — so the six of ten default
 * feeds seeded under security and technology could never be ranked at all,
 * and the section silently hid most of the feed list. There is no whitelist
 * here: every enabled feed appears, under its own category.
 *
 * §4.2: ranking now covers every section (§1.4), so a weight here genuinely
 * orders that category's list. §4.3: each group says how many of its feeds
 * can be ranked, and flags the sections with ranking switched off.
 */
export default function FeedRankings({ rankedSlugs }: FeedRankingsProps) {
  const [feeds, setFeeds] = useState<Feed[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [weights, setWeights] = useState<Record<number, number>>({});
  const [open, setOpen] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    const res = await fetch("/api/feeds/weights");
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      setMsg({ ok: false, text: apiErrorMessage(data, "Could not load feed weights.") });
      return;
    }
    const data = await res.json();
    const loaded: Feed[] = data.feeds || [];
    setFeeds(loaded);
    const next: Record<number, number> = {};
    loaded.forEach((f) => { next[f.id] = f.sourceWeight ?? DEFAULT_WEIGHT; });
    setWeights(next);

    const catRes = await fetch("/api/categories");
    if (catRes.ok) setCategories(await catRes.json());
  }

  async function updateFeedWeight(feedId: number, weight: number) {
    setMsg(null);
    const res = await fetch("/api/feeds/weights", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ feedId, weight }),
    });
    // §3.4: this used to update local state only when res.ok and show nothing
    // otherwise, so a rejected change (out-of-range, unknown feed, the
    // protected Manual Links feed) made the select snap back with no
    // explanation at all. The failure is now reported.
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      setMsg({ ok: false, text: apiErrorMessage(data, "Could not update that weight.") });
      return;
    }
    setWeights((w) => ({ ...w, [feedId]: weight }));
    setMsg({ ok: true, text: "Weight saved." });
  }

  /** Feeds grouped by category, in the sidebar's category order. */
  const groups = useMemo(() => {
    const byCategory = new Map<string, Feed[]>();
    for (const f of feeds) {
      const key = f.categorySlug ?? "unknown";
      const list = byCategory.get(key);
      if (list) list.push(f);
      else byCategory.set(key, [f]);
    }
    return categories
      .filter((c) => byCategory.has(c.slug))
      .map((c) => ({ ...c, feeds: byCategory.get(c.slug) ?? [] }));
  }, [feeds, categories]);

  return (
    <div className="settings-section">
      <div className="settings-section-head">
        <div className="settings-section-title">Feed Rankings</div>
        <div className="settings-section-sub">
          Higher weight → more likely to appear in top articles
        </div>
      </div>
      <div className="settings-body">
        {msg && <div className={`settings-msg ${msg.ok ? "ok" : "err"}`}>{msg.text}</div>}

        <button className="tb-btn" onClick={() => setOpen((o) => !o)} style={{ marginBottom: 6 }}>
          {open ? "▲ Hide feeds" : "▼ Show feed weights"}
        </button>

        {open && (
          <div className="feed-rankings-list">
            {groups.map((g) => {
              const ranked = rankedSlugs.has(g.slug);
              return (
                <div key={g.slug} className="feed-rankings-group">
                  <div className="feed-rankings-head">
                    <span className="feed-rankings-title">{g.name}</span>
                    <span className="feed-rankings-count">
                      {g.feeds.length} feed{g.feeds.length === 1 ? "" : "s"}
                      {ranked ? " · ranked" : " · ranking off"}
                    </span>
                  </div>
                  {!ranked && (
                    <div className="feed-rankings-note">
                      Ranking is off for {g.name}, so weights here are stored but do not
                      change the order. Turn it on under Ranking below.
                    </div>
                  )}
                  {g.feeds.map((f) => (
                    <div key={f.id} className="feed-row">
                      <span className="feed-name">{f.name}</span>
                      <select
                        className="feed-select"
                        value={presetValue(weights[f.id] ?? DEFAULT_WEIGHT)}
                        onChange={(e) => void updateFeedWeight(f.id, presetWeight(e.target.value))}
                        aria-label={`Ranking weight for ${f.name}`}
                      >
                        {WEIGHT_PRESETS.map((p) => (
                          <option key={p.weight} value={presetValue(p.weight)}>
                            {p.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}