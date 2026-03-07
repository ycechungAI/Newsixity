"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  searchParams?: Record<string, string | undefined>;
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

export default function Pagination({ currentPage, totalPages, searchParams = {} }: PaginationProps) {
  const pathname = usePathname();
  if (totalPages <= 1) return null;

  const start = Math.max(1, currentPage - 2);
  const end   = Math.min(totalPages, currentPage + 2);
  const pages: number[] = [];
  for (let i = start; i <= end; i++) pages.push(i);

  const path = pathname || "/";

  return (
    <div className="pagination">
      {currentPage > 1
        ? <Link href={buildHref(currentPage - 1, searchParams, path)} className="pg-btn">‹ Prev</Link>
        : <span className="pg-btn" style={{ opacity: .4 }}>‹ Prev</span>}

      {start > 1 && (
        <>
          <Link href={buildHref(1, searchParams, path)} className="pg-btn">1</Link>
          {start > 2 && <span style={{ color: "var(--subtle)", padding: "0 2px" }}>…</span>}
        </>
      )}

      {pages.map(p =>
        p === currentPage
          ? <span key={p} className="pg-btn current">{p}</span>
          : <Link key={p} href={buildHref(p, searchParams, path)} className="pg-btn">{p}</Link>
      )}

      {end < totalPages && (
        <>
          {end < totalPages - 1 && <span style={{ color: "var(--subtle)", padding: "0 2px" }}>…</span>}
          <Link href={buildHref(totalPages, searchParams, path)} className="pg-btn">{totalPages}</Link>
        </>
      )}

      {currentPage < totalPages
        ? <Link href={buildHref(currentPage + 1, searchParams, path)} className="pg-btn">Next ›</Link>
        : <span className="pg-btn" style={{ opacity: .4 }}>Next ›</span>}
    </div>
  );
}
