"""Per-route fixed-window rate limiter.

Direct port of src/lib/server/rate-limit.ts. Node applies rate limiting inside
each route handler with an explicit ``routeKey``/``limit``/``windowMs``; we
mirror that by attaching a ``rate_limit(...)`` dependency to each route so the
config lives on the route, exactly as in the Node source.

State is an in-process dict of buckets, matching Node's module-level ``Map``.
Under a single-worker asyncio event loop this is race-free the same way Node's
single-threaded model is; running multiple workers gives each its own buckets,
identical to running multiple Node instances.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

from fastapi import Request

# Window durations in milliseconds (Node uses ms epochs throughout).
TEN_MIN_MS = 10 * 60 * 1000
ONE_HOUR_MS = 60 * 60 * 1000

_MAX_BUCKETS = 5000


class RateLimitExceeded(Exception):
    """Raised when a client exceeds a route's limit.

    Handled centrally (app.main) to produce Node's exact 429 body shape
    ``{"error": "Rate limit exceeded", "retryAfter": N}`` plus a ``Retry-After``
    header — FastAPI's HTTPException would nest the body under ``detail``.
    """

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__("Rate limit exceeded")


@dataclass
class _Bucket:
    count: int
    reset_at: float  # ms epoch
    last_seen: float  # ms epoch


_buckets: dict[str, _Bucket] = {}


def _now_ms() -> float:
    return time.time() * 1000


def _get_client_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
        if ip:
            return ip

    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip

    return "local"


def _cleanup_buckets(now: float) -> None:
    if len(_buckets) <= _MAX_BUCKETS:
        return

    # Drop stale entries first.
    stale = [key for key, bucket in _buckets.items() if now - bucket.last_seen > ONE_HOUR_MS]
    for key in stale:
        _buckets.pop(key, None)

    # If still too large, evict oldest entries.
    if len(_buckets) <= _MAX_BUCKETS:
        return
    ordered = sorted(_buckets.items(), key=lambda kv: kv[1].last_seen)
    remove_count = len(_buckets) - _MAX_BUCKETS
    for key, _ in ordered[:remove_count]:
        _buckets.pop(key, None)


def enforce_rate_limit(request: Request, route_key: str, limit: int, window_ms: int) -> None:
    """Increment the client's bucket for ``route_key``; raise if over ``limit``."""
    now = _now_ms()
    client = _get_client_key(request)
    key = f"{route_key}:{client}"
    existing = _buckets.get(key)

    if existing is None or now >= existing.reset_at:
        bucket = _Bucket(count=1, reset_at=now + window_ms, last_seen=now)
    else:
        bucket = _Bucket(count=existing.count + 1, reset_at=existing.reset_at, last_seen=now)

    _buckets[key] = bucket
    _cleanup_buckets(now)

    if bucket.count <= limit:
        return

    retry_after_seconds = max(1, math.ceil((bucket.reset_at - now) / 1000))
    raise RateLimitExceeded(retry_after_seconds)


def rate_limit(route_key: str, limit: int, window_ms: int):
    """Build a FastAPI dependency enforcing ``limit`` requests per ``window_ms``.

    Usage::

        @router.get("/thing", dependencies=[Depends(rate_limit("thing-get", 120, TEN_MIN_MS))])
    """

    async def _dependency(request: Request) -> None:
        enforce_rate_limit(request, route_key, limit, window_ms)

    return _dependency
