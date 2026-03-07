"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type ViewMode =
  | "topics"
  | "cards"
  | "compact"
  | "sources"
  | "timeline"
  | "list";

interface ViewModeToggleProps {
  viewMode: ViewMode;
  searchParams?: Record<string, string | undefined>;
}

const MODES: { value: ViewMode; label: string }[] = [
  { value: "topics", label: "Topics" },
  { value: "cards", label: "Cards" },
  { value: "list", label: "List" },
  { value: "sources", label: "Sources" },
  { value: "timeline", label: "Timeline" },
];

function buildHref(
  mode: ViewMode,
  current: Record<string, string | undefined>,
  pathname: string,
): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(current)) {
    if (k === "view" || k === "page" || !v) continue;
    params.set(k, v);
  }
  if (mode !== "topics") params.set("view", mode);
  const qs = params.toString();
  return qs ? `${pathname}?${qs}` : pathname;
}

export default function ViewModeToggle({
  viewMode,
  searchParams = {},
}: ViewModeToggleProps) {
  const pathname = usePathname();

  return (
    <div className="toolbar">
      {MODES.map((m) => (
        <Link
          key={m.value}
          href={buildHref(m.value, searchParams, pathname || "/")}
          className={`tb-btn${viewMode === m.value ? " active" : ""}`}
        >
          {m.label}
        </Link>
      ))}
    </div>
  );
}
