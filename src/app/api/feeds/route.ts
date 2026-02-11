import { NextResponse } from "next/server";
import {
  getArticlesByCategory,
  getArticleGroupsByCategory,
  searchArticles,
} from "@/lib/db/queries";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const category = searchParams.get("category") || undefined;
    const limit = parseInt(searchParams.get("limit") || "50", 10);
    const offset = parseInt(searchParams.get("offset") || "0", 10);
    const grouped = searchParams.get("grouped") === "true";
    const search = searchParams.get("search") || undefined;

    if (search) {
      const results = searchArticles(search, { category, limit });
      return NextResponse.json({ articles: results });
    }

    if (grouped) {
      const groups = getArticleGroupsByCategory(category ?? null, limit);
      return NextResponse.json({ groups });
    }

    const articles = getArticlesByCategory(category ?? null, { limit, offset });
    return NextResponse.json({ articles });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
