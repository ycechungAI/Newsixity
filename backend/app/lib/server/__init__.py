"""Server-side request-gating middleware.

Ports src/lib/server/{auth,rate-limit}.ts:
- ``auth``: loopback-trust + token + CSRF/origin checks (applied globally as
  ASGI middleware over ``/api/*``, mirroring src/proxy.ts).
- ``rate_limit``: per-route fixed-window limiter (applied as a FastAPI
  dependency on each route, mirroring the per-handler ``enforceRateLimit``
  calls in the Node routes).
"""

from app.lib.server.auth import ApiAccessResult, check_api_access
from app.lib.server.rate_limit import (
    ONE_HOUR_MS,
    TEN_MIN_MS,
    RateLimitExceeded,
    enforce_rate_limit,
    rate_limit,
)

__all__ = [
    "ApiAccessResult",
    "check_api_access",
    "ONE_HOUR_MS",
    "TEN_MIN_MS",
    "RateLimitExceeded",
    "enforce_rate_limit",
    "rate_limit",
]
