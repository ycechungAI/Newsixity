"""API access control — loopback trust, token auth, CSRF/origin checks.

Direct port of src/lib/server/auth.ts. Applied globally over ``/api/*`` as ASGI
middleware (see app.main), mirroring src/proxy.ts which runs ``checkApiAccess``
in Next's middleware with ``/api/health`` as the only public path.

Behavior parity notes:
- Mutating methods must pass CSRF (sec-fetch-site) and same-origin checks
  regardless of how they later authenticate.
- A request from a loopback host is trusted without a token ("local mode").
- Outside local mode, ``NEWSIXITY_ADMIN_TOKEN`` / ``NEWSIXITY_API_TOKEN`` gate
  access, with admin paths always requiring the admin token.
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass

from starlette.requests import Request

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
ADMIN_PATH_PREFIXES = (
    "/api/console",
    "/api/settings",
    "/api/feeds/refresh",
    "/api/feeds/weights",
    "/api/summarize",
    "/api/preferences",
)
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_SAME_SITE_VALUES = {"same-origin", "same-site", "none"}


@dataclass
class ApiAccessResult:
    ok: bool
    status: int | None = None
    error: str | None = None


def _normalize_host(raw_host: str | None) -> str:
    if not raw_host:
        return ""
    host = raw_host.split(",")[0].strip().lower()

    if host.startswith("["):
        end = host.find("]")
        if end > 1:
            return host[1:end]

    return host.split(":")[0]


def _get_request_host(request: Request) -> str:
    raw = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    return raw.split(",")[0].strip().lower()


def _is_loopback_ip(ip: str) -> bool:
    value = ip.strip().lower()
    if not value:
        return False
    if value in ("::1", "0:0:0:0:0:0:0:1"):
        return True
    if value.startswith("127."):
        return True
    if value.startswith("::ffff:"):
        mapped = value[len("::ffff:") :]
        return mapped == "::1" or mapped.startswith("127.")
    return False


def _is_trusted_local_request(request: Request) -> bool:
    request_host = _normalize_host(_get_request_host(request))
    if request_host not in LOCAL_HOSTS:
        return False

    # If forwarded IP is present, require loopback.
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
        if not _is_loopback_ip(ip):
            return False

    return True


def _is_mutating_method(method: str) -> bool:
    return method.upper() not in _SAFE_METHODS


def _is_cross_site_request(request: Request) -> bool:
    site = request.headers.get("sec-fetch-site")
    if not site:
        return False
    return site not in _SAME_SITE_VALUES


def _has_same_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return True

    try:
        from urllib.parse import urlsplit

        origin_host = urlsplit(origin).netloc.lower()
        if not origin_host:
            return False
        return origin_host == _get_request_host(request)
    except Exception:
        return False


def _get_presented_token(request: Request) -> str:
    authorization = request.headers.get("authorization")
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()

    return (request.headers.get("x-newsixity-token") or "").strip()


def _is_admin_path(pathname: str) -> bool:
    return any(
        pathname == prefix or pathname.startswith(f"{prefix}/")
        for prefix in ADMIN_PATH_PREFIXES
    )


def _timing_safe_equal(left: str, right: str) -> bool:
    if len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def _has_token_access(request: Request, pathname: str) -> bool:
    admin_token = (os.environ.get("NEWSIXITY_ADMIN_TOKEN") or "").strip()
    api_token = (os.environ.get("NEWSIXITY_API_TOKEN") or "").strip()
    token = _get_presented_token(request)

    # No configured tokens means "local-only" mode.
    if not admin_token and not api_token:
        return False

    if _is_admin_path(pathname):
        # Admin routes always require an explicit admin token outside local mode.
        if not admin_token:
            return False
        return _timing_safe_equal(token, admin_token)

    if api_token:
        return _timing_safe_equal(token, api_token)

    # If only admin token is configured, allow it for non-admin routes.
    if admin_token:
        return _timing_safe_equal(token, admin_token)

    return False


def check_api_access(request: Request) -> ApiAccessResult:
    pathname = request.url.path

    if _is_mutating_method(request.method):
        if _is_cross_site_request(request):
            return ApiAccessResult(ok=False, status=403, error="Cross-site requests are not allowed")
        if not _has_same_origin(request):
            return ApiAccessResult(ok=False, status=403, error="Origin mismatch")

    if _is_trusted_local_request(request):
        return ApiAccessResult(ok=True)

    if _has_token_access(request, pathname):
        return ApiAccessResult(ok=True)

    return ApiAccessResult(ok=False, status=401, error="Unauthorized API access")
