"""Security tests for API access control (app/lib/server/auth.py).

Port of tests/security/auth.test.ts. Covers:
 - Trusted local requests (localhost) are allowed without tokens
 - Cross-site mutation requests are blocked (CSRF)
 - Origin-mismatch mutation requests are blocked
 - Remote requests without valid tokens are rejected (401)
 - Token-based access works for read and admin paths
 - Admin paths require an admin token; API-only token is insufficient

Requests are built as raw ASGI scopes fed into starlette.requests.Request,
mirroring the duck-typed mock used in the Node test (no real ASGI server
needed since check_api_access only reads method/url/headers).
"""

import pytest
from starlette.requests import Request

from app.lib.server.auth import check_api_access


def make_request(url: str, method: str = "GET", headers: dict[str, str] | None = None) -> Request:
    from urllib.parse import urlsplit

    parsed = urlsplit(url)
    raw_headers = [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": method.upper(),
        "path": parsed.path or "/",
        "raw_path": (parsed.path or "/").encode("latin-1"),
        "query_string": parsed.query.encode("latin-1"),
        "headers": raw_headers,
        "scheme": parsed.scheme or "http",
        "server": (parsed.hostname or "localhost", parsed.port or 80),
        "client": ("testclient", 12345),
        "http_version": "1.1",
    }
    return Request(scope)


def local_get(path: str, extra: dict[str, str] | None = None) -> Request:
    return make_request(f"http://localhost{path}", headers={"host": "localhost", **(extra or {})})


def local_post(path: str, extra: dict[str, str] | None = None) -> Request:
    return make_request(
        f"http://localhost{path}", method="POST", headers={"host": "localhost", **(extra or {})}
    )


def remote_get(path: str, token: str | None = None, extra: dict[str, str] | None = None) -> Request:
    headers = {"host": "newsixity.example.com", **(extra or {})}
    if token:
        headers["authorization"] = f"Bearer {token}"
    return make_request(f"https://newsixity.example.com{path}", headers=headers)


@pytest.fixture(autouse=True)
def clean_token_env(monkeypatch):
    monkeypatch.delenv("NEWSIXITY_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("NEWSIXITY_API_TOKEN", raising=False)


class TestTrustedLocalRequests:
    def test_allows_get_from_localhost_without_token(self):
        result = check_api_access(local_get("/api/articles"))
        assert result.ok is True

    def test_allows_post_from_localhost_with_no_origin_header(self):
        result = check_api_access(local_post("/api/articles"))
        assert result.ok is True

    def test_allows_get_from_127_0_0_1_host(self):
        req = make_request("http://127.0.0.1/api/articles", headers={"host": "127.0.0.1"})
        assert check_api_access(req).ok is True

    def test_rejects_when_x_forwarded_for_is_external_ip(self):
        req = make_request(
            "http://localhost/api/articles",
            headers={"host": "localhost", "x-forwarded-for": "203.0.113.42"},
        )
        result = check_api_access(req)
        assert result.ok is False
        assert result.status == 401


class TestCsrfProtectionCrossSiteMutations:
    def test_blocks_post_with_sec_fetch_site_cross_site(self):
        req = local_post("/api/articles", {"sec-fetch-site": "cross-site"})
        result = check_api_access(req)
        assert result.ok is False
        assert result.status == 403

    def test_allows_post_with_sec_fetch_site_same_origin(self):
        req = local_post("/api/articles", {"sec-fetch-site": "same-origin"})
        assert check_api_access(req).ok is True

    def test_blocks_post_with_mismatched_origin_header(self):
        req = make_request(
            "http://localhost/api/articles",
            method="POST",
            headers={"host": "localhost", "origin": "https://evil.example.com"},
        )
        result = check_api_access(req)
        assert result.ok is False
        assert result.status == 403

    def test_allows_post_with_matching_origin_header(self):
        req = make_request(
            "http://localhost/api/articles",
            method="POST",
            headers={"host": "localhost", "origin": "http://localhost"},
        )
        assert check_api_access(req).ok is True

    def test_does_not_apply_csrf_check_to_get_requests(self):
        req = local_get("/api/articles", {"sec-fetch-site": "cross-site"})
        assert check_api_access(req).ok is True


class TestRemoteRequestsNoTokenConfigured:
    def test_rejects_remote_get_when_no_token_configured(self):
        result = check_api_access(remote_get("/api/articles"))
        assert result.ok is False
        assert result.status == 401

    def test_rejects_remote_get_even_with_token_header_when_none_configured(self):
        result = check_api_access(remote_get("/api/articles", "some-token"))
        assert result.ok is False
        assert result.status == 401


class TestTokenBasedAccess:
    def test_allows_remote_get_with_valid_api_token(self, monkeypatch):
        monkeypatch.setenv("NEWSIXITY_API_TOKEN", "valid-api-token")
        assert check_api_access(remote_get("/api/articles", "valid-api-token")).ok is True

    def test_rejects_remote_get_with_wrong_api_token(self, monkeypatch):
        monkeypatch.setenv("NEWSIXITY_API_TOKEN", "valid-api-token")
        result = check_api_access(remote_get("/api/articles", "wrong-token"))
        assert result.ok is False
        assert result.status == 401

    def test_allows_remote_get_with_valid_admin_token_on_non_admin_path(self, monkeypatch):
        monkeypatch.setenv("NEWSIXITY_ADMIN_TOKEN", "admin-secret")
        assert check_api_access(remote_get("/api/articles", "admin-secret")).ok is True

    def test_accepts_token_via_x_newsixity_token_header(self, monkeypatch):
        monkeypatch.setenv("NEWSIXITY_API_TOKEN", "header-token-xyz")
        req = make_request(
            "https://newsixity.example.com/api/articles",
            headers={"host": "newsixity.example.com", "x-newsixity-token": "header-token-xyz"},
        )
        assert check_api_access(req).ok is True


class TestAdminPathProtection:
    def test_allows_admin_token_on_console(self, monkeypatch):
        monkeypatch.setenv("NEWSIXITY_ADMIN_TOKEN", "admin-secret")
        assert check_api_access(remote_get("/api/console", "admin-secret")).ok is True

    def test_rejects_api_only_token_on_console(self, monkeypatch):
        monkeypatch.setenv("NEWSIXITY_ADMIN_TOKEN", "admin-secret")
        monkeypatch.setenv("NEWSIXITY_API_TOKEN", "api-only-token")
        result = check_api_access(remote_get("/api/console", "api-only-token"))
        assert result.ok is False
        assert result.status == 401

    def test_rejects_api_only_token_on_settings(self, monkeypatch):
        monkeypatch.setenv("NEWSIXITY_ADMIN_TOKEN", "admin-secret")
        monkeypatch.setenv("NEWSIXITY_API_TOKEN", "api-only-token")
        result = check_api_access(remote_get("/api/settings", "api-only-token"))
        assert result.ok is False
        assert result.status == 401

    def test_allows_admin_token_on_settings(self, monkeypatch):
        monkeypatch.setenv("NEWSIXITY_ADMIN_TOKEN", "admin-secret")
        assert check_api_access(remote_get("/api/settings", "admin-secret")).ok is True

    def test_allows_admin_token_on_feeds_refresh(self, monkeypatch):
        monkeypatch.setenv("NEWSIXITY_ADMIN_TOKEN", "admin-secret")
        assert check_api_access(remote_get("/api/feeds/refresh", "admin-secret")).ok is True

    def test_rejects_no_token_remote_request_on_admin_path(self, monkeypatch):
        monkeypatch.setenv("NEWSIXITY_ADMIN_TOKEN", "admin-secret")
        result = check_api_access(remote_get("/api/console"))
        assert result.ok is False
        assert result.status == 401
