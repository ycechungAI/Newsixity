type ViewMode =
  | "topics"
  | "cards"
  | "compact"
  | "sources"
  | "timeline"
  | "list";

interface ViewModeToggleProps {
  viewMode: ViewMode;
  onChange: (mode: ViewMode) => void;
}

const MODES: { value: ViewMode; label: string }[] = [
  { value: "topics", label: "Topics" },
  { value: "cards", label: "Cards" },
  { value: "list", label: "List" },
  { value: "sources", label: "Sources" },
  { value: "timeline", label: "Timeline" },
];

export default function ViewModeToggle({ viewMode, onChange }: ViewModeToggleProps) {
  return (
    <div className="toolbar">
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
