import { useEffect, useState } from "react";
import { apiErrorMessage } from "@/lib/utils/apiError";

interface ScoreWeights {
  groupSize: number;
  preferenceMatch: number;
  sourceWeight: number;
  recency: number;
  titleImportance: number;
}

interface RankingSettings {
  categorySlug: string;
  feedSoftCap: number;
  feedHardCap: number;
  promoteLimit: number;
  ranked: boolean;
  weights: ScoreWeights;
}

interface Category {
  slug: string;
  name: string;
}

export interface RankingDefaults {
  feedSoftCap: number;
  feedHardCap: number;
  weights: ScoreWeights;
}

/** The five score signals, in the order they're shown.
 *
 * The keys are the API's, and the labels say what each one measures rather
 * than repeating the key — a slider labelled "groupSize" tells the user
 * nothing about what raising it does to their feed.
 */
const WEIGHT_FIELDS: { key: keyof ScoreWeights; label: string; hint: string }[] = [
  { key: "groupSize", label: "Covered by several outlets", hint: "Higher when more sources carry the same story" },
  { key: "preferenceMatch", label: "Matches your interests", hint: "Learned from the articles you save" },
  { key: "sourceWeight", label: "Source weight", hint: "Your Feed Rankings dials, per feed" },
  { key: "recency", label: "Recency", hint: "Full within 6h, fading by 24h" },
  { key: "titleImportance", label: "Headline importance", hint: "Breaking, exclusive, urgent…" },
];

const MAX_CAPS = 100;
const MAX_PROMOTE = 500;

interface RankingSettingsPanelProps {
  /** Called after a save so Feed Rankings can re-read which sections are on. */
  onSaved?: () => void;
}

/** Settings › Ranking: what each section stores, promotes, and weights by.
 *
 * spec-v0.5 §5. These were module constants (CATEGORY_DAILY_INSERT_CAP,
 * DAILY_ARTICLE_LIMIT, and the scorer's five literals) with no surface
 * anywhere, so a user who wanted more or fewer articles per day had no way to
 * ask for it. §5.3 is the constraint that matters: a section with no stored
 * row reads back as exactly the v0.4 values, so this panel never silently
 * changes scoring for anyone who doesn't touch it.
 */
export default function RankingSettingsPanel({ onSaved }: RankingSettingsPanelProps) {
  const [settings, setSettings] = useState<RankingSettings[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [savingSlug, setSavingSlug] = useState<string | null>(null);

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    const [settingsRes, catRes] = await Promise.all([
      fetch("/api/ranking/settings"),
      fetch("/api/categories"),
    ]);
    if (!settingsRes.ok) {
      const data = await settingsRes.json().catch(() => null);
      setMsg({ ok: false, text: apiErrorMessage(data, "Could not load ranking settings.") });
      return;
    }
    const data = await settingsRes.json();
    setSettings(data.settings || []);
    if (catRes.ok) setCategories(await catRes.json());
  }

  function patch(slug: string, changes: Partial<RankingSettings>) {
    setSettings((prev) =>
      prev.map((s) => (s.categorySlug === slug ? { ...s, ...changes } : s))
    );
  }

  function patchWeight(slug: string, key: keyof ScoreWeights, value: number) {
    setSettings((prev) =>
      prev.map((s) =>
        s.categorySlug === slug
          ? { ...s, weights: { ...s.weights, [key]: value } }
          : s
      )
    );
  }

  async function save(s: RankingSettings) {
    setSavingSlug(s.categorySlug);
    setMsg(null);
    const total = Object.values(s.weights).reduce((a, b) => a + b, 0);
    if (total !== 100) {
      setMsg({
        ok: false,
        text: `${s.categorySlug}: score weights add up to ${total}, not 100.`,
      });
      setSavingSlug(null);
      return;
    }
    try {
      const res = await fetch(`/api/ranking/settings/${encodeURIComponent(s.categorySlug)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          feedSoftCap: s.feedSoftCap,
          feedHardCap: s.feedHardCap,
          promoteLimit: s.promoteLimit,
          ranked: s.ranked,
          weights: s.weights,
        }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setMsg({ ok: false, text: apiErrorMessage(data, "Could not save those settings.") });
        return;
      }
      setMsg({ ok: true, text: "Ranking settings saved." });
      onSaved?.();
    } catch {
      setMsg({ ok: false, text: "Could not reach the Newsixity backend." });
    } finally {
      setSavingSlug(null);
    }
  }

  const nameOf = (slug: string) => categories.find((c) => c.slug === slug)?.name ?? slug;

  return (
    <div className="settings-section">
      <div className="settings-section-head">
        <div className="settings-section-title">Ranking</div>
        <div className="settings-section-sub">
          How much each section stores per day, how many articles it promotes, and what
          the score is made of
        </div>
      </div>
      <div className="settings-body">
        {msg && <div className={`settings-msg ${msg.ok ? "ok" : "err"}`}>{msg.text}</div>}

        {settings.map((s) => {
          const total = Object.values(s.weights).reduce((a, b) => a + b, 0);
          const saving = savingSlug === s.categorySlug;
          return (
            <div key={s.categorySlug} className="ranking-row">
              <div className="ranking-row-head">
                <span className="ranking-row-title">{nameOf(s.categorySlug)}</span>
                <label className="ranking-ranked-toggle">
                  <input
                    type="checkbox"
                    checked={s.ranked}
                    onChange={(e) => patch(s.categorySlug, { ranked: e.target.checked })}
                  />
                  Ranked
                </label>
              </div>

              <div className="ranking-caps">
                <label>
                  <span>Soft cap / feed</span>
                  <input
                    type="number"
                    className="settings-input"
                    min={0}
                    max={MAX_CAPS}
                    value={s.feedSoftCap}
                    onChange={(e) =>
                      patch(s.categorySlug, { feedSoftCap: Number(e.target.value) })
                    }
                  />
                </label>
                <label>
                  <span>Hard cap / feed</span>
                  <input
                    type="number"
                    className="settings-input"
                    min={0}
                    max={MAX_CAPS}
                    value={s.feedHardCap}
                    onChange={(e) =>
                      patch(s.categorySlug, { feedHardCap: Number(e.target.value) })
                    }
                  />
                </label>
                <label>
                  <span>Promote / day</span>
                  <input
                    type="number"
                    className="settings-input"
                    min={1}
                    max={MAX_PROMOTE}
                    value={s.promoteLimit}
                    onChange={(e) =>
                      patch(s.categorySlug, { promoteLimit: Number(e.target.value) })
                    }
                  />
                </label>
              </div>

              <div className="ranking-weights">
                {WEIGHT_FIELDS.map((f) => (
                  <label key={f.key} className="ranking-weight" title={f.hint}>
                    <span className="ranking-weight-label">{f.label}</span>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      value={s.weights[f.key]}
                      onChange={(e) =>
                        patchWeight(s.categorySlug, f.key, Number(e.target.value))
                      }
                    />
                    <span className="ranking-weight-value">{s.weights[f.key]}</span>
                  </label>
                ))}
                <div className={`ranking-weight-total${total === 100 ? "" : " is-bad"}`}>
                  Weights total {total} (must be 100)
                </div>
              </div>

              <button
                className="tb-btn"
                onClick={() => void save(s)}
                disabled={saving || total !== 100}
              >
                {saving ? "Saving…" : `Save ${nameOf(s.categorySlug)}`}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}