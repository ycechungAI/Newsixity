"use client";

import { useRouter } from "next/navigation";

interface CategoryTab {
  slug: string;
  name: string;
  total: number;
  unread: number;
}

interface CategoryTabsProps {
  categories: CategoryTab[];
  activeSlug?: string;
  basePath?: string;
  preserveParams?: Record<string, string | undefined>;
}

export default function CategoryTabs({
  categories,
  activeSlug,
  basePath = "/",
  preserveParams = {},
}: CategoryTabsProps) {
  const router = useRouter();

  function buildUrl(categorySlug?: string) {
    if (categorySlug === "weather" && basePath === "/") return "/weather";
    if (categorySlug === "finance" && basePath === "/") return "/finance";
    const params = new URLSearchParams();
    Object.entries(preserveParams).forEach(([k, v]) => { if (v) params.set(k, v); });
    if (categorySlug) params.set("category", categorySlug);
    const qs = params.toString();
    return qs ? `${basePath}?${qs}` : basePath;
  }

  return (
    <div className="toolbar" style={{ marginBottom: 8, overflowX: "auto", flexWrap: "nowrap" }}>
      <button
        onClick={() => router.push(buildUrl())}
        className={`tb-btn${!activeSlug ? " active" : ""}`}
      >All</button>
      {categories.map((cat) => (
        <button
          key={cat.slug}
          onClick={() => router.push(buildUrl(cat.slug))}
          className={`tb-btn${activeSlug === cat.slug ? " active" : ""}`}
        >
          {cat.name}
          {cat.unread > 0 && <span className="nav-badge" style={{ marginLeft: 3 }}>{cat.unread}</span>}
        </button>
      ))}
    </div>
  );
}
