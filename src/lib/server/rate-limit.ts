import { NextResponse } from "next/server";

type Bucket = {
  count: number;
  resetAt: number;
  lastSeen: number;
};

const buckets = new Map<string, Bucket>();
const MAX_BUCKETS = 5000;

function getClientKey(request: Request): string {
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor) {
    const ip = forwardedFor.split(",")[0]?.trim();
    if (ip) return ip;
  }

  const realIp = request.headers.get("x-real-ip")?.trim();
  if (realIp) return realIp;

  return "local";
}

function cleanupBuckets(now: number): void {
  if (buckets.size <= MAX_BUCKETS) return;

  for (const [key, bucket] of buckets) {
    // Drop stale entries first.
    if (now - bucket.lastSeen > 60 * 60 * 1000) {
      buckets.delete(key);
    }
  }

  // If still too large, evict oldest entries.
  if (buckets.size <= MAX_BUCKETS) return;
  const sorted = [...buckets.entries()].sort((a, b) => a[1].lastSeen - b[1].lastSeen);
  const removeCount = buckets.size - MAX_BUCKETS;
  for (let i = 0; i < removeCount; i++) {
    buckets.delete(sorted[i][0]);
  }
}

export function enforceRateLimit(
  request: Request,
  options: {
    routeKey: string;
    limit: number;
    windowMs: number;
  }
): NextResponse | null {
  const now = Date.now();
  const client = getClientKey(request);
  const key = `${options.routeKey}:${client}`;
  const existing = buckets.get(key);

  let bucket: Bucket;
  if (!existing || now >= existing.resetAt) {
    bucket = {
      count: 1,
      resetAt: now + options.windowMs,
      lastSeen: now,
    };
  } else {
    bucket = {
      ...existing,
      count: existing.count + 1,
      lastSeen: now,
    };
  }

  buckets.set(key, bucket);
  cleanupBuckets(now);

  if (bucket.count <= options.limit) {
    return null;
  }

  const retryAfterSeconds = Math.max(1, Math.ceil((bucket.resetAt - now) / 1000));
  return NextResponse.json(
    {
      error: "Rate limit exceeded",
      retryAfter: retryAfterSeconds,
    },
    {
      status: 429,
      headers: {
        "Retry-After": String(retryAfterSeconds),
      },
    }
  );
}

