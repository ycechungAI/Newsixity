/** Feed ranking weight presets — spec-v0.5 3.5.
 *
 * One list drives both the `<option>` values and the label formatter, because
 * those two drifting apart is the bug that shipped: React matches `<select>`
 * values as strings, so `String(1.0)` is `"1"` while the option's value was
 * `"1.0"`. A feed set to Normal matched no option, the browser fell back to
 * the first one, and the UI displayed **Low** while the database held 1.0.
 * Picking Normal then appeared not to stick.
 *
 * The range is exactly what the API accepts and exactly what `score_article`
 * reads (0.5–2.0), so a stored weight is always the weight that was scored.
 */

export interface WeightPreset {
  /** The stored weight. Serialised to one decimal — see `presetValue`. */
  weight: number;
  label: string;
}

export const WEIGHT_PRESETS: readonly WeightPreset[] = [
  { weight: 0.5, label: "Low (0.5×)" },
  { weight: 1.0, label: "Normal (1.0×)" },
  { weight: 1.5, label: "High (1.5×)" },
  { weight: 2.0, label: "Essential (2.0×)" },
] as const;

export const DEFAULT_WEIGHT = 1.0;

/** The string form used for `<option value>` and `<select value>`.
 *
 * Both sides go through this, so they cannot disagree about how a weight is
 * spelled. `.toFixed(1)` also means a stored weight outside the presets (0.7,
 * say) has no matching option and falls through to the browser's own default,
 * rather than silently displaying whichever preset happens to be first.
 */
export function presetValue(weight: number): string {
  return weight.toFixed(1);
}

/** The stored weight for a select's string value. */
export function presetWeight(value: string): number {
  return parseFloat(value);
}