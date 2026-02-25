import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  stripHtml,
  truncate,
  extractImageFromHtml,
} from "../../src/lib/utils/sanitize.ts";

describe("stripHtml", () => {
  it("removes block-level HTML tags", () => {
    assert.equal(stripHtml("<p>Hello world</p>"), "Hello world");
  });

  it("removes inline HTML tags", () => {
    assert.equal(stripHtml("<p>Hello <b>world</b></p>"), "Hello world");
  });

  it("decodes &amp;", () => {
    assert.equal(stripHtml("&amp;"), "&");
  });

  it("decodes &lt; and &gt;", () => {
    assert.equal(stripHtml("&lt;div&gt;"), "<div>");
  });

  it("decodes &quot;", () => {
    assert.equal(stripHtml("&quot;hello&quot;"), '"hello"');
  });

  it("decodes &#39;", () => {
    assert.equal(stripHtml("&#39;it&#39;s"), "'it's");
  });

  it("normalizes internal whitespace to single space", () => {
    assert.equal(stripHtml("foo   bar"), "foo bar");
  });

  it("trims leading and trailing whitespace", () => {
    assert.equal(stripHtml("  hello  "), "hello");
  });

  it("returns empty string for empty input", () => {
    assert.equal(stripHtml(""), "");
  });

  it("returns plain text unchanged (minus whitespace normalization)", () => {
    assert.equal(stripHtml("plain text"), "plain text");
  });

  it("handles nested tags", () => {
    assert.equal(
      stripHtml("<div><span><em>deep</em></span></div>"),
      "deep"
    );
  });

  it("handles tags with attributes", () => {
    assert.equal(
      stripHtml('<a href="https://example.com" class="link">click</a>'),
      "click"
    );
  });
});

describe("truncate", () => {
  it("returns original text when shorter than maxLength", () => {
    assert.equal(truncate("hello", 10), "hello");
  });

  it("returns original text when equal to maxLength", () => {
    assert.equal(truncate("hello", 5), "hello");
  });

  it("truncates long text and appends ellipsis", () => {
    const result = truncate("abcdefghijklmnopqrstuvwxyz", 10);
    assert.ok(result.endsWith("..."));
  });

  it("truncates at word boundary when last space is past 80% mark", () => {
    // "hello world" = 11 chars, maxLength=8, 80% of 8=6.4, last space at index 5 > 6.4? No.
    // Let's use: "foo bar baz" (11), maxLength=9, 80% of 9=7.2, "foo bar" fits at index 7 > 7.2
    const result = truncate("foo bar baz", 9);
    // lastSpace in "foo bar b" is at index 7, 7 > 9*0.8=7.2 → false → hard cut
    assert.equal(result, "foo bar b...");
  });

  it("breaks at word boundary when space is after 80% mark", () => {
    // "hello world test" (16), maxLength=12, 80% of 12=9.6
    // slice(0,12) = "hello world ", lastSpace at 11, 11 > 9.6 → true → word-break
    const result = truncate("hello world test", 12);
    assert.equal(result, "hello world...");
  });

  it("returns single char plus ellipsis for tiny maxLength", () => {
    const result = truncate("hello world", 1);
    assert.equal(result, "h...");
  });
});

describe("extractImageFromHtml", () => {
  it("extracts src from an img tag with double quotes", () => {
    assert.equal(
      extractImageFromHtml('<img src="https://example.com/image.jpg" />'),
      "https://example.com/image.jpg"
    );
  });

  it("extracts src from an img tag with single quotes", () => {
    assert.equal(
      extractImageFromHtml("<img src='https://example.com/photo.png'>"),
      "https://example.com/photo.png"
    );
  });

  it("extracts src when img has other attributes before src", () => {
    assert.equal(
      extractImageFromHtml('<img alt="Photo" src="https://example.com/a.jpg">'),
      "https://example.com/a.jpg"
    );
  });

  it("returns null when there is no img tag", () => {
    assert.equal(extractImageFromHtml("<p>No image here</p>"), null);
  });

  it("returns null for empty string", () => {
    assert.equal(extractImageFromHtml(""), null);
  });

  it("returns the first img src when multiple images exist", () => {
    assert.equal(
      extractImageFromHtml(
        '<img src="https://example.com/first.jpg"><img src="https://example.com/second.jpg">'
      ),
      "https://example.com/first.jpg"
    );
  });
});
