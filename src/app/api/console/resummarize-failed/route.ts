import { NextResponse } from "next/server";
import { resetFailedAndSkippedArticles } from "@/lib/db/queries";
import { enforceRateLimit } from "@/lib/server/rate-limit";

export async function POST(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "console-resummarize-failed",
    limit: 10,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const result = resetFailedAndSkippedArticles();
    return NextResponse.json({ 
      success: true, 
      count: result.count,
      message: `Reset ${result.count} failed/skipped articles for resummrization` 
    });
  } catch (e) {
    console.error("Console resummarize-failed error:", e);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
