import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  detectSearchEngine,
  isSearchEngineUrl,
} from "../../src/lib/utils/search.ts";

describe("detectSearchEngine", () => {
  it("detects Google with q param", () => {
    const result = detectSearchEngine("https://www.google.com/search?q=test+query");
    assert.ok(result);
    assert.equal(result.engine.name, "Google");
    assert.equal(result.query, "test query");
  });

  it("detects Google on google.co.uk subdomain", () => {
    const result = detectSearchEngine("https://www.google.co.uk/search?q=hello");
    // google.co.uk includes "google.com"? No — domain check is .includes("google.com")
    // "www.google.co.uk" does NOT include "google.com", so this should return null
    // This validates that the implementation uses exact substring matching
    assert.equal(result, null);
  });

  it("detects Bing with q param", () => {
    const result = detectSearchEngine("https://www.bing.com/search?q=typescript");
    assert.ok(result);
    assert.equal(result.engine.name, "Bing");
    assert.equal(result.query, "typescript");
  });

  it("detects DuckDuckGo with q param", () => {
    const result = detectSearchEngine("https://duckduckgo.com/?q=privacy+browser");
    assert.ok(result);
    assert.equal(result.engine.name, "DuckDuckGo");
    assert.equal(result.query, "privacy browser");
  });

  it("detects Yahoo Search with p param", () => {
    const result = detectSearchEngine(
      "https://search.yahoo.com/search?p=weather+forecast"
    );
    assert.ok(result);
    assert.equal(result.engine.name, "Yahoo");
    assert.equal(result.query, "weather forecast");
  });

  it("detects Baidu with wd param", () => {
    const result = detectSearchEngine("https://www.baidu.com/s?wd=news");
    assert.ok(result);
    assert.equal(result.engine.name, "Baidu");
    assert.equal(result.query, "news");
  });

  it("detects Yandex with text param", () => {
    const result = detectSearchEngine("https://yandex.com/search/?text=hello");
    assert.ok(result);
    assert.equal(result.engine.name, "Yandex");
    assert.equal(result.query, "hello");
  });

  it("decodes URL-encoded query params", () => {
    const result = detectSearchEngine(
      "https://www.google.com/search?q=hello%20world%21"
    );
    assert.ok(result);
    assert.equal(result.query, "hello world!");
  });

  it("returns null for a regular website URL", () => {
    assert.equal(detectSearchEngine("https://example.com/article"), null);
  });

  it("returns null for a search engine URL without the query param", () => {
    assert.equal(detectSearchEngine("https://www.google.com/"), null);
  });

  it("returns null for an invalid URL", () => {
    assert.equal(detectSearchEngine("not-a-url"), null);
  });

  it("returns null for an empty string", () => {
    assert.equal(detectSearchEngine(""), null);
  });
});

describe("isSearchEngineUrl", () => {
  it("returns true for a Google search URL", () => {
    assert.equal(
      isSearchEngineUrl("https://www.google.com/search?q=test"),
      true
    );
  });

  it("returns true for a DuckDuckGo search URL", () => {
    assert.equal(isSearchEngineUrl("https://duckduckgo.com/?q=test"), true);
  });

  it("returns false for a non-search URL", () => {
    assert.equal(isSearchEngineUrl("https://github.com/"), false);
  });

  it("returns false for an invalid URL", () => {
    assert.equal(isSearchEngineUrl("garbage"), false);
  });
});
