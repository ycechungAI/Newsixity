import { NextResponse } from "next/server";
import { getCategories, getArticleCountByCategory } from "@/lib/db/queries";
import { internalServerError } from "@/lib/server/api-response";

export async function GET() {
  try {
    const categories = getCategories();
    const counts = getArticleCountByCategory();

    // Build a lookup map from slug to counts
    const countMap = new Map(
      counts.map((c) => [c.slug, { total: c.total, unread: c.unread }])
    );

    // Merge counts into category objects
    const result = categories.map((cat) => {
      const count = countMap.get(cat.slug);
      return {
        ...cat,
        total: count?.total ?? 0,
        unread: count?.unread ?? 0,
      };
    });

    return NextResponse.json(result);
  } catch (e) {
    return internalServerError("Categories GET error", e);
  }
}
