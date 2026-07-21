"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { Suspense } from "react";

type SavedViewMode = "cards" | "compact" | "list" | "categories" | "sources" | "timeline";

interface SavedViewModeToggleProps {
  viewMode: SavedViewMode;
  onChange?: (mode: SavedViewMode) => void;
}

const MODES: { value: SavedViewMode; label: string }[] = [
  { value: "cards",      label: "Cards"     },
  { value: "list",       label: "List"      },
  { value: "sources",    label: "Sources"   },
  { value: "timeline",   label: "Timeline"  },
  { value: "categories", label: "Categories"},
];

function SavedViewModeToggleContent({ viewMode, onChange }: SavedViewModeToggleProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathname = usePathname();

  function handleModeChange(mode: SavedViewMode) {
    if (onChange) {
      onChange(mode);
      return;
    }
    const params = new URLSearchParams(searchParams.toString());
    if (mode === "cards") params.delete("view");
    else params.set("view", mode);
    params.delete("page");
    const query = params.toString();
    router.push(query ? `${pathname}?${query}` : pathname);
  }

  return (
    <div className="toolbar" style={{ marginBottom: 0 }}>
      {MODES.map((m) => (
        <button
          key={m.value}
          onClick={() => handleModeChange(m.value)}
          className={`tb-btn${viewMode === m.value ? " active" : ""}`}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}

export default function SavedViewModeToggle(props: SavedViewModeToggleProps) {
  if (props.onChange) {
    // If using onChange (client-side state), render directly without useSearchParams
    return (
      <div className="toolbar" style={{ marginBottom: 0 }}>
        {MODES.map((m) => (
          <button
            key={m.value}
            onClick={() => props.onChange!(m.value)}
            className={`tb-btn${props.viewMode === m.value ? " active" : ""}`}
          >
            {m.label}
          </button>
        ))}
      </div>
    );
  }
  // If not using onChange (server-side routing), wrap in Suspense
  return (
    <Suspense fallback={<div className="toolbar" style={{ marginBottom: 0 }} />}>
      <SavedViewModeToggleContent {...props} />
    </Suspense>
  );
}
