"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";

type SavedViewMode = "cards" | "compact" | "list" | "categories" | "sources" | "timeline";

interface SavedViewModeToggleProps {
  viewMode: SavedViewMode;
}

const MODES: { value: SavedViewMode; label: string }[] = [
  { value: "cards",      label: "Cards"     },
  { value: "list",       label: "List"      },
  { value: "sources",    label: "Sources"   },
  { value: "timeline",   label: "Timeline"  },
  { value: "categories", label: "Categories"},
];

export default function SavedViewModeToggle({ viewMode }: SavedViewModeToggleProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathname = usePathname();

  function handleModeChange(mode: SavedViewMode) {
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
