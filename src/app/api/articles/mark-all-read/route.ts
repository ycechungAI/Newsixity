import { NextResponse } from "next/server";
import { markAllReadByCategory } from "@/lib/db/queries";

export async function POST(request: Request) {
  try {
    let category: string | null = null;
    try {
      const body = await request.json();
      category = body.category ?? null;
    } catch {
      // empty body = mark all
    }

    const count = markAllReadByCategory(category);
    return NextResponse.json({ success: true, marked: count, category });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
