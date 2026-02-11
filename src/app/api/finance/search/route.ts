import { NextResponse } from "next/server";
import { searchYahooStocks } from "@/lib/finance/yahoo";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const query = searchParams.get("query");

    if (!query || query.trim().length === 0) {
      return NextResponse.json(
        { error: "Query parameter is required" },
        { status: 400 }
      );
    }

    const results = await searchYahooStocks(query.trim());

    return NextResponse.json({ results });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    console.error("[Newsixity] Stock search error:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
