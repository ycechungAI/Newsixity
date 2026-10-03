import { useState } from "react";

/** Human labels for the five score signals (spec-v0.5 6.2).
 *
 * Keyed by the API's field names. The label says what the signal measures,
 * not what the column is called — "groupSize" tells a reader nothing about
 * why their article is at the top.
 */
const PART_LABELS: Record<string, string> = {
  groupSize: "Covered by several outlets",
  preferenceMatch: "Matches what you save",
  sourceWeight: "Source weight",
  recency: "Recency",
  titleImportance: "Headline importance",
};

const PART_ORDER = [
  "groupSize",
  "preferenceMatch",
  "sourceWeight",
  "recency",
  "titleImportance",
];

interface ScoreExplainerProps {
  score: number;
  parts?: Record<string, number> | null;
}

/** The ranking score, with its five contributions on hover.
 *
 * A score nobody can interrogate gets ignored (spec-v0.5 §6): before this,
 * `relevance_score` drove the order of every list and nothing on screen said
 * why. Hovering the number shows what each signal contributed, so an article
 * at the top because five outlets carried it says so.
 *
 * Renders nothing when there are no parts — an article scored before parts
 * were recorded has no explanation to give, and inventing one would be worse
 * than showing the score alone.
 */
export default function ScoreExplainer({ score, parts }: ScoreExplainerProps) {
  const [open, setOpen] = useState(false);
  if (!parts || Object.keys(parts).length === 0) return null;

  const keys = PART_ORDER.filter((k) => typeof parts[k] === "number");
  if (keys.length === 0) return null;

  return (
    <span
      className="score-explainer"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      tabIndex={0}
      aria-label={`Ranking score ${score.toFixed(1)} of 100`}
    >
      <span className="score-value">{score.toFixed(1)}</span>
      {open && (
        <span className="score-parts" role="tooltip">
          <span className="score-parts-title">Why this ranks here</span>
          {keys.map((key) => (
            <span key={key} className="score-part">
              <span className="score-part-label">{PART_LABELS[key] ?? key}</span>
              <span className="score-bar">
                <span
                  className="score-bar-fill"
                  style={{ width: `${Math.max(0, Math.min(100, (parts[key] ?? 0)))}%` }}
                />
              </span>
              <span className="score-part-value">{(parts[key] ?? 0).toFixed(1)}</span>
            </span>
          ))}
          <span className="score-parts-foot">Total {score.toFixed(1)} of 100</span>
        </span>
      )}
    </span>
  );
}