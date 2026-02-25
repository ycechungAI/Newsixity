import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { parseHttpUrl, isHttpUrl } from "../../src/lib/utils/url.ts";

describe("parseHttpUrl", () => {
  it("returns a URL object for a valid https URL", () => {
    const result = parseHttpUrl("https://example.com/path");
    assert.ok(result instanceof URL);
    assert.equal(result.href, "https://example.com/path");
  });

  it("returns a URL object for a valid http URL", () => {
    const result = parseHttpUrl("http://example.com");
    assert.ok(result instanceof URL);
    assert.equal(result.protocol, "http:");
  });

  it("returns null for null input", () => {
    assert.equal(parseHttpUrl(null), null);
  });

  it("returns null for undefined input", () => {
    assert.equal(parseHttpUrl(undefined), null);
  });

  it("returns null for an empty string", () => {
    assert.equal(parseHttpUrl(""), null);
  });

  it("returns null for a whitespace-only string", () => {
    assert.equal(parseHttpUrl("   "), null);
  });

  it("trims whitespace before parsing", () => {
    const result = parseHttpUrl("  https://example.com  ");
    assert.ok(result instanceof URL);
  });

  it("returns null for ftp:// protocol", () => {
    assert.equal(parseHttpUrl("ftp://files.example.com"), null);
  });

  it("returns null for file:// protocol", () => {
    assert.equal(parseHttpUrl("file:///etc/passwd"), null);
  });

  it("returns null for data: URI", () => {
    assert.equal(parseHttpUrl("data:text/html,<h1>test</h1>"), null);
  });

  it("returns null for javascript: URI", () => {
    assert.equal(parseHttpUrl("javascript:alert(1)"), null);
  });

  it("returns null for a URL containing credentials (username)", () => {
    assert.equal(parseHttpUrl("https://user@example.com"), null);
  });

  it("returns null for a URL containing credentials (username:password)", () => {
    assert.equal(parseHttpUrl("https://user:pass@example.com"), null);
  });

  it("returns null for a malformed URL", () => {
    assert.equal(parseHttpUrl("not a url"), null);
  });

  it("preserves query parameters", () => {
    const result = parseHttpUrl("https://example.com/search?q=test&page=2");
    assert.ok(result instanceof URL);
    assert.equal(result.searchParams.get("q"), "test");
    assert.equal(result.searchParams.get("page"), "2");
  });

  it("preserves URL path", () => {
    const result = parseHttpUrl("https://example.com/a/b/c");
    assert.ok(result instanceof URL);
    assert.equal(result.pathname, "/a/b/c");
  });
});

describe("isHttpUrl", () => {
  it("returns true for a valid https URL", () => {
    assert.equal(isHttpUrl("https://example.com"), true);
  });

  it("returns true for a valid http URL", () => {
    assert.equal(isHttpUrl("http://example.com"), true);
  });

  it("returns false for null", () => {
    assert.equal(isHttpUrl(null), false);
  });

  it("returns false for an empty string", () => {
    assert.equal(isHttpUrl(""), false);
  });

  it("returns false for ftp://", () => {
    assert.equal(isHttpUrl("ftp://example.com"), false);
  });

  it("returns false for credential-bearing URLs", () => {
    assert.equal(isHttpUrl("https://user:pass@example.com"), false);
  });

  it("returns false for javascript: URI", () => {
    assert.equal(isHttpUrl("javascript:void(0)"), false);
  });
});
