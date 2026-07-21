/**
 * Security tests for API access control (src/lib/server/auth.ts).
 *
 * Tests cover:
 *  - Trusted local requests (localhost) are allowed without tokens
 *  - Cross-site mutation requests are blocked (CSRF)
 *  - Origin-mismatch mutation requests are blocked
 *  - Remote requests without valid tokens are rejected (401)
 *  - Token-based access works for read and admin paths
 *  - Admin paths require an admin token; API-only token is insufficient
 *
 * NextRequest is mocked with a plain object that matches the duck-typed
 * interface used by checkApiAccess — no next/server import needed at runtime
 * because auth.ts uses `import type` (stripped by --experimental-strip-types).
 */
import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { checkApiAccess } from "../../src/lib/server/auth.ts";

// ---------------------------------------------------------------------------
// Minimal NextRequest-compatible mock
// ---------------------------------------------------------------------------

function mockRequest(
  url: string,
  options: { method?: string; headers?: Record<string, string> } = {}
) {
  const parsed = new URL(url);
  const headers = new Headers(options.headers ?? {});
  return {
    method: (options.method ?? "GET").toUpperCase(),
    nextUrl: { pathname: parsed.pathname },
    headers: {
      get: (name: string) => headers.get(name),
    },
  };
}

// Convenience builders
function localGet(path: string, extra: Record<string, string> = {}) {
  return mockRequest(`http://localhost${path}`, {
    headers: { host: "localhost", ...extra },
  });
}

function localPost(path: string, extra: Record<string, string> = {}) {
  return mockRequest(`http://localhost${path}`, {
    method: "POST",
    headers: { host: "localhost", ...extra },
  });
}

function remoteGet(path: string, token?: string, extra: Record<string, string> = {}) {
  const headers: Record<string, string> = { host: "newsixity.example.com", ...extra };
  if (token) headers["authorization"] = `Bearer ${token}`;
  return mockRequest(`https://newsixity.example.com${path}`, { headers });
}

// ---------------------------------------------------------------------------
// Save/restore env so tests are isolated
// ---------------------------------------------------------------------------

let savedAdmin: string | undefined;
let savedApi: string | undefined;

beforeEach(() => {
  savedAdmin = process.env.NEWSIXITY_ADMIN_TOKEN;
  savedApi = process.env.NEWSIXITY_API_TOKEN;
  delete process.env.NEWSIXITY_ADMIN_TOKEN;
  delete process.env.NEWSIXITY_API_TOKEN;
});

afterEach(() => {
  if (savedAdmin === undefined) delete process.env.NEWSIXITY_ADMIN_TOKEN;
  else process.env.NEWSIXITY_ADMIN_TOKEN = savedAdmin;
  if (savedApi === undefined) delete process.env.NEWSIXITY_API_TOKEN;
  else process.env.NEWSIXITY_API_TOKEN = savedApi;
});

// ---------------------------------------------------------------------------
// Trusted local requests
// ---------------------------------------------------------------------------

describe("Trusted local requests", () => {
  it("allows GET from localhost without a token", () => {
    const result = checkApiAccess(localGet("/api/articles") as never);
    assert.equal(result.ok, true);
  });

  it("allows POST from localhost with no origin header", () => {
    const result = checkApiAccess(localPost("/api/articles") as never);
    assert.equal(result.ok, true);
  });

  it("allows GET from 127.0.0.1 host", () => {
    const req = mockRequest("http://127.0.0.1/api/articles", {
      headers: { host: "127.0.0.1" },
    });
    assert.equal(checkApiAccess(req as never).ok, true);
  });

  it("rejects when x-forwarded-for is an external IP (even with localhost host)", () => {
    const req = mockRequest("http://localhost/api/articles", {
      headers: { host: "localhost", "x-forwarded-for": "203.0.113.42" },
    });
    const result = checkApiAccess(req as never);
    assert.equal(result.ok, false);
    assert.equal(result.status, 401);
  });
});

// ---------------------------------------------------------------------------
// CSRF protection – cross-site mutations
// ---------------------------------------------------------------------------

describe("CSRF protection – cross-site mutations", () => {
  it("blocks POST with sec-fetch-site: cross-site", () => {
    const req = localPost("/api/articles", { "sec-fetch-site": "cross-site" });
    const result = checkApiAccess(req as never);
    assert.equal(result.ok, false);
    assert.equal(result.status, 403);
  });

  it("allows POST with sec-fetch-site: same-origin", () => {
    const req = localPost("/api/articles", { "sec-fetch-site": "same-origin" });
    assert.equal(checkApiAccess(req as never).ok, true);
  });

  it("blocks POST with a mismatched origin header", () => {
    const req = mockRequest("http://localhost/api/articles", {
      method: "POST",
      headers: { host: "localhost", origin: "https://evil.example.com" },
    });
    const result = checkApiAccess(req as never);
    assert.equal(result.ok, false);
    assert.equal(result.status, 403);
  });

  it("allows POST with matching origin header", () => {
    const req = mockRequest("http://localhost/api/articles", {
      method: "POST",
      headers: { host: "localhost", origin: "http://localhost" },
    });
    assert.equal(checkApiAccess(req as never).ok, true);
  });

  it("does not apply CSRF check to GET requests (sec-fetch-site ignored)", () => {
    const req = localGet("/api/articles", { "sec-fetch-site": "cross-site" });
    // Trusted local GET should still pass; CSRF checks only apply to mutations
    assert.equal(checkApiAccess(req as never).ok, true);
  });
});

// ---------------------------------------------------------------------------
// Remote requests – no token configured
// ---------------------------------------------------------------------------

describe("Remote requests – no token configured", () => {
  it("rejects remote GET when no token is configured", () => {
    const result = checkApiAccess(remoteGet("/api/articles") as never);
    assert.equal(result.ok, false);
    assert.equal(result.status, 401);
  });

  it("rejects remote GET even when a token header is sent (but none configured)", () => {
    const result = checkApiAccess(remoteGet("/api/articles", "some-token") as never);
    assert.equal(result.ok, false);
    assert.equal(result.status, 401);
  });
});

// ---------------------------------------------------------------------------
// Token-based access
// ---------------------------------------------------------------------------

describe("Token-based access", () => {
  it("allows remote GET with a valid API token", () => {
    process.env.NEWSIXITY_API_TOKEN = "valid-api-token";
    assert.equal(checkApiAccess(remoteGet("/api/articles", "valid-api-token") as never).ok, true);
  });

  it("rejects remote GET with a wrong API token", () => {
    process.env.NEWSIXITY_API_TOKEN = "valid-api-token";
    const result = checkApiAccess(remoteGet("/api/articles", "wrong-token") as never);
    assert.equal(result.ok, false);
    assert.equal(result.status, 401);
  });

  it("allows remote GET with a valid admin token on a non-admin path", () => {
    process.env.NEWSIXITY_ADMIN_TOKEN = "admin-secret";
    assert.equal(checkApiAccess(remoteGet("/api/articles", "admin-secret") as never).ok, true);
  });

  it("accepts token via x-newsixity-token header", () => {
    process.env.NEWSIXITY_API_TOKEN = "header-token-xyz";
    const req = mockRequest("https://newsixity.example.com/api/articles", {
      headers: { host: "newsixity.example.com", "x-newsixity-token": "header-token-xyz" },
    });
    assert.equal(checkApiAccess(req as never).ok, true);
  });
});

// ---------------------------------------------------------------------------
// Admin path protection
// ---------------------------------------------------------------------------

describe("Admin path protection", () => {
  it("allows admin token on /api/console", () => {
    process.env.NEWSIXITY_ADMIN_TOKEN = "admin-secret";
    assert.equal(checkApiAccess(remoteGet("/api/console", "admin-secret") as never).ok, true);
  });

  it("rejects API-only token on /api/console (admin path)", () => {
    process.env.NEWSIXITY_ADMIN_TOKEN = "admin-secret";
    process.env.NEWSIXITY_API_TOKEN = "api-only-token";
    const result = checkApiAccess(remoteGet("/api/console", "api-only-token") as never);
    assert.equal(result.ok, false);
    assert.equal(result.status, 401);
  });

  it("rejects API-only token on /api/settings", () => {
    process.env.NEWSIXITY_ADMIN_TOKEN = "admin-secret";
    process.env.NEWSIXITY_API_TOKEN = "api-only-token";
    const result = checkApiAccess(remoteGet("/api/settings", "api-only-token") as never);
    assert.equal(result.ok, false);
    assert.equal(result.status, 401);
  });

  it("allows admin token on /api/settings", () => {
    process.env.NEWSIXITY_ADMIN_TOKEN = "admin-secret";
    assert.equal(checkApiAccess(remoteGet("/api/settings", "admin-secret") as never).ok, true);
  });

  it("allows admin token on /api/feeds/refresh", () => {
    process.env.NEWSIXITY_ADMIN_TOKEN = "admin-secret";
    assert.equal(
      checkApiAccess(remoteGet("/api/feeds/refresh", "admin-secret") as never).ok,
      true
    );
  });

  it("rejects no-token remote request on admin path", () => {
    process.env.NEWSIXITY_ADMIN_TOKEN = "admin-secret";
    const result = checkApiAccess(remoteGet("/api/console") as never);
    assert.equal(result.ok, false);
    assert.equal(result.status, 401);
  });
});
