type SavedViewMode = "cards" | "compact" | "list" | "categories" | "sources" | "timeline";

interface SavedViewModeToggleProps {
  viewMode: SavedViewMode;
  onChange: (mode: SavedViewMode) => void;
}

const MODES: { value: SavedViewMode; label: string }[] = [
  { value: "cards",      label: "Cards"     },
  { value: "list",       label: "List"      },
  { value: "sources",    label: "Sources"   },
  { value: "timeline",   label: "Timeline"  },
  { value: "categories", label: "Categories"},
];

export default function SavedViewModeToggle({ viewMode, onChange }: SavedViewModeToggleProps) {
  return (
    <div className="toolbar" style={{ marginBottom: 0 }}>
      {MODES.map((m) => (
        <button
          key={m.value}
          onClick={() => onChange(m.value)}
          className={`tb-btn${viewMode === m.value ? " active" : ""}`}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}
