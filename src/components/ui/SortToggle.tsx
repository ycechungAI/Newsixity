import { useState } from "react";

export type SortMode = "relevance" | "recent" | "source";

interface SortToggleProps {
  value: SortMode;
  onChange: (value: SortMode) => void;
  /** False where ranking isn't in play (e.g. Saved), so the control hides. */
  available?: boolean;
}

const OPTIONS: { value: SortMode; label: string; title: string }[] = [
  {
    value: "relevance",
    label: "Top",
    title: "Best-scoring first — an article covered by several outlets or matching what you save outranks a merely recent one",
  },
  {
    value: "recent",
    label: "Newest",
    title: "Strictly newest first",
  },
  {
    value: "source",
    label: "By source",
    title: "One outlet's articles together, oldest section first",
  },
];

/** Per-view article ordering, next to the view-mode toggle (spec-v0.5 1.2).
 *
 * A per-view decision rather than a preference, so it lives in the list header
 * instead of Settings. "Top" is the default on the server; this only makes the
 * choice visible and reversible.
 */
export default function SortToggle({ value, onChange, available = true }: SortToggleProps) {
  const [open, setOpen] = useState(false);
  if (!available) return null;

  const current = OPTIONS.find((o) => o.value === value) ?? OPTIONS[0];

  return (
    <div className="sort-toggle">
      <button
        className="tb-btn"
        onClick={() => setOpen((o) => !o)}
        title="Order articles"
        aria-expanded={open}
      >
        Order: {current.label}
      </button>
      {open && (
        <div className="sort-toggle-menu">
          {OPTIONS.map((o) => (
            <button
              key={o.value}
              className={`sort-toggle-option${o.value === value ? " is-active" : ""}`}
              title={o.title}
              onClick={() => { onChange(o.value); setOpen(false); }}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}