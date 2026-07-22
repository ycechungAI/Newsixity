interface CategoryTab {
  slug: string;
  name: string;
  total: number;
  unread: number;
}

interface CategoryTabsProps {
  categories: CategoryTab[];
  activeSlug?: string | null;
  onSelectCategory: (slug: string | null) => void;
}

export default function CategoryTabs({
  categories,
  activeSlug,
  onSelectCategory,
}: CategoryTabsProps) {
  return (
    <div className="toolbar" style={{ marginBottom: 8, overflowX: "auto", flexWrap: "nowrap" }}>
      <button
        onClick={() => onSelectCategory(null)}
        className={`tb-btn${!activeSlug ? " active" : ""}`}
      >All</button>
      {categories.map((cat) => (
        <button
          key={cat.slug}
          onClick={() => onSelectCategory(cat.slug)}
          className={`tb-btn${activeSlug === cat.slug ? " active" : ""}`}
        >
          {cat.name}
          {cat.unread > 0 && <span className="nav-badge" style={{ marginLeft: 3 }}>{cat.unread}</span>}
        </button>
      ))}
    </div>
  );
}
