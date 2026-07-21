import CategoryPageClient from "./CategoryPageClient";

// Static export requires build-time knowledge of dynamic route params.
// Kept in sync manually with the backend's seeded categories
// (see backend/app/lib/rss/feeds.py DEFAULT_FEEDS / get_categories()).
// "weather" and "finance" are excluded: they redirect to their own
// dedicated pages client-side.
const CATEGORY_SLUGS = [
  "world-news",
  "top-news",
  "gaming",
  "technology",
  "sports",
  "others",
];

export function generateStaticParams() {
  return CATEGORY_SLUGS.map((slug) => ({ slug }));
}

export default async function CategoryPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  // key={slug} forces a full remount (fresh loading/currentPage state)
  // when navigating between categories client-side.
  return <CategoryPageClient key={slug} slug={slug} />;
}
