import type { NextRequest } from "next/server";

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "::1"]);
const ADMIN_PATH_PREFIXES = [
  "/api/console",
  "/api/settings",
  "/api/feeds/refresh",
  "/api/feeds/weights",
  "/api/summarize",
  "/api/preferences",
];

function normalizeHost(rawHost: string | null): string {
  if (!rawHost) return "";
  const host = rawHost.split(",")[0].trim().toLowerCase();

  if (host.startsWith("[")) {
    const end = host.indexOf("]");
    if (end > 1) {
      return host.slice(1, end);
    }
  }

  return host.split(":")[0];
}

function getRequestHost(request: NextRequest): string {
  return (
    request.headers.get("x-forwarded-host") ??
    request.headers.get("host") ??
    ""
  )
    .split(",")[0]
    .trim()
    .toLowerCase();
}

function isLoopbackIp(ip: string): boolean {
  const value = ip.trim().toLowerCase();
  if (!value) return false;
  if (value === "::1" || value === "0:0:0:0:0:0:0:1") return true;
  if (value.startsWith("127.")) return true;
  if (value.startsWith("::ffff:")) {
    const mapped = value.slice("::ffff:".length);
    return mapped === "::1" || mapped.startsWith("127.");
  }
  return false;
}

function isTrustedLocalRequest(request: NextRequest): boolean {
  const requestHost = normalizeHost(getRequestHost(request));
  if (!LOCAL_HOSTS.has(requestHost)) {
    return false;
  }

  // If forwarded IP is present, require loopback.
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor) {
    const ip = forwardedFor.split(",")[0]?.trim() ?? "";
    if (!isLoopbackIp(ip)) {
      return false;
    }
  }

  return true;
}

function isMutatingMethod(method: string): boolean {
  return !["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase());
}

function isCrossSiteRequest(request: NextRequest): boolean {
  const site = request.headers.get("sec-fetch-site");
  if (!site) return false;
  return !["same-origin", "same-site", "none"].includes(site);
}

function hasSameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return true;

  try {
    const originHost = new URL(origin).host.toLowerCase();
    return originHost === getRequestHost(request);
  } catch {
    return false;
  }
}

function timingSafeEqual(left: string, right: string): boolean {
  if (left.length !== right.length) return false;
  let mismatch = 0;
  for (let i = 0; i < left.length; i++) {
    mismatch |= left.charCodeAt(i) ^ right.charCodeAt(i);
  }
  return mismatch === 0;
}

function getPresentedToken(request: NextRequest): string {
  const authorization = request.headers.get("authorization");
  if (authorization?.toLowerCase().startsWith("bearer ")) {
    return authorization.slice(7).trim();
  }

  return (request.headers.get("x-newsixity-token") ?? "").trim();
}

function isAdminPath(pathname: string): boolean {
  return ADMIN_PATH_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
}

function hasTokenAccess(request: NextRequest, pathname: string): boolean {
  const adminToken = process.env.NEWSIXITY_ADMIN_TOKEN?.trim();
  const apiToken = process.env.NEWSIXITY_API_TOKEN?.trim();
  const token = getPresentedToken(request);

  // No configured tokens means "local-only" mode.
  if (!adminToken && !apiToken) return false;

  if (isAdminPath(pathname)) {
    // Admin routes always require an explicit admin token outside local mode.
    if (!adminToken) return false;
    return timingSafeEqual(token, adminToken);
  }

  if (apiToken) {
    return timingSafeEqual(token, apiToken);
  }

  // If only admin token is configured, allow it for non-admin routes.
  if (adminToken) {
    return timingSafeEqual(token, adminToken);
  }

  return false;
}

export function checkApiAccess(request: NextRequest): {
  ok: boolean;
  status?: 401 | 403;
  error?: string;
} {
  const pathname = request.nextUrl.pathname;

  if (isMutatingMethod(request.method)) {
    if (isCrossSiteRequest(request)) {
      return { ok: false, status: 403, error: "Cross-site requests are not allowed" };
    }
    if (!hasSameOrigin(request)) {
      return { ok: false, status: 403, error: "Origin mismatch" };
    }
  }

  if (isTrustedLocalRequest(request)) {
    return { ok: true };
  }

  if (hasTokenAccess(request, pathname)) {
    return { ok: true };
  }

  return { ok: false, status: 401, error: "Unauthorized API access" };
}
