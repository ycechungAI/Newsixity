"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  searchParams?: Record<string, string | undefined>;
  onChange?: (page: number) => void;
}

function buildHref(page: number, current: Record<string, string | undefined>, pathname: string): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(current)) {
    if (k === "page" || !v) continue;
    params.set(k, v);
  }
  if (page > 1) params.set("page", String(page));
  const qs = params.toString();
  return qs ? `${pathname}?${qs}` : pathname;
}

export default function Pagination({ currentPage, totalPages, searchParams = {}, onChange }: PaginationProps) {
  const pathname = usePathname();
  if (totalPages <= 1) return null;

  const start = Math.max(1, currentPage - 2);
  const end   = Math.min(totalPages, currentPage + 2);
  const pages: number[] = [];
  for (let i = start; i <= end; i++) pages.push(i);

  const path = pathname || "/";

  const renderButton = (page: number, label: React.ReactNode, isDisabled = false, key?: React.Key) => {
    if (onChange && !isDisabled) {
      return (
        <button
          key={key}
          onClick={() => onChange(page)}
          className="pg-btn"
        >
          {label}
        </button>
      );
    }
    if (isDisabled) {
      return <span key={key} className="pg-btn" style={{ opacity: .4 }}>{label}</span>;
    }
    return (
      <Link key={key} href={buildHref(page, searchParams, path)} className="pg-btn">
        {label}
      </Link>
    );
  };

  return (
    <div className="pagination">
      {renderButton(currentPage - 1, "‹ Prev", currentPage <= 1)}

      {start > 1 && (
        <>
          {renderButton(1, "1")}
          {start > 2 && <span style={{ color: "var(--subtle)", padding: "0 2px" }}>…</span>}
        </>
      )}

      {pages.map(p =>
        p === currentPage
          ? <span key={p} className="pg-btn current">{p}</span>
          : renderButton(p, p, false, p)
      )}

      {end < totalPages && (
        <>
          {end < totalPages - 1 && <span style={{ color: "var(--subtle)", padding: "0 2px" }}>…</span>}
          {renderButton(totalPages, totalPages)}
        </>
      )}

      {renderButton(currentPage + 1, "Next ›", currentPage >= totalPages)}
    </div>
  );
}
