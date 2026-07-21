import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { checkApiAccess } from "@/lib/server/auth";

const PUBLIC_API_PATHS = new Set(["/api/health"]);

export function proxy(request: NextRequest) {
  if (!request.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.next();
  }

  if (PUBLIC_API_PATHS.has(request.nextUrl.pathname)) {
    return NextResponse.next();
  }

  const access = checkApiAccess(request);
  if (!access.ok) {
    return NextResponse.json(
      { error: access.error ?? "Unauthorized" },
      { status: access.status ?? 401 }
    );
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/api/:path*"],
};
