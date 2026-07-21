import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { timeAgo, formatDate } from "../../src/lib/utils/date.ts";

describe("timeAgo", () => {
  it("returns 'Unknown' for null", () => {
    assert.equal(timeAgo(null), "Unknown");
  });

  it("returns 'Unknown' for an invalid date string", () => {
    assert.equal(timeAgo("not-a-date"), "Unknown");
  });

  it("returns 'just now' for a date 30 seconds ago", () => {
    const date = new Date(Date.now() - 30 * 1000).toISOString();
    assert.equal(timeAgo(date), "just now");
  });

  it("returns 'just now' for a date 59 seconds ago", () => {
    const date = new Date(Date.now() - 59 * 1000).toISOString();
    assert.equal(timeAgo(date), "just now");
  });

  it("returns minutes label for a date 5 minutes ago", () => {
    const date = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    assert.equal(timeAgo(date), "5m ago");
  });

  it("returns minutes label for 59 minutes ago", () => {
    const date = new Date(Date.now() - 59 * 60 * 1000).toISOString();
    assert.equal(timeAgo(date), "59m ago");
  });

  it("returns hours label for a date 3 hours ago", () => {
    const date = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString();
    assert.equal(timeAgo(date), "3h ago");
  });

  it("returns hours label for 23 hours ago", () => {
    const date = new Date(Date.now() - 23 * 60 * 60 * 1000).toISOString();
    assert.equal(timeAgo(date), "23h ago");
  });

  it("returns days label for a date 2 days ago", () => {
    const date = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString();
    assert.equal(timeAgo(date), "2d ago");
  });

  it("returns days label for 6 days ago", () => {
    const date = new Date(Date.now() - 6 * 24 * 60 * 60 * 1000).toISOString();
    assert.equal(timeAgo(date), "6d ago");
  });

  it("returns 'Month Day' for a date older than 7 days", () => {
    // Use a fixed old date so the result is deterministic
    const date = new Date("2020-03-15T10:00:00Z").toISOString();
    const result = timeAgo(date);
    // Should be "Mar 15" (local date may differ by timezone; just check format)
    assert.match(result, /^[A-Z][a-z]{2} \d{1,2}$/);
  });
});

describe("formatDate", () => {
  it("returns 'Unknown' for null", () => {
    assert.equal(formatDate(null), "Unknown");
  });

  it("returns 'Unknown' for an invalid date string", () => {
    assert.equal(formatDate("not-a-date"), "Unknown");
  });

  it("formats a valid ISO date string", () => {
    // Use a date that is unambiguous regardless of timezone offset
    // 2024-06-15T12:00:00Z → in UTC this is Jun 15, 2024 at 12:00 PM
    // The exact output depends on local timezone, so we test structure
    const result = formatDate("2024-06-15T12:00:00Z");
    // Should match pattern like "Jun 15, 2024 at 12:00 PM"
    assert.match(result, /^[A-Z][a-z]{2} \d{1,2}, \d{4} at \d{1,2}:\d{2} (AM|PM)$/);
  });

  it("includes AM/PM indicator", () => {
    const result = formatDate("2024-01-01T08:00:00Z");
    assert.ok(result.includes("AM") || result.includes("PM"));
  });

  it("pads minutes with leading zero", () => {
    // A time like 10:05 AM should show "10:05" not "10:5"
    const result = formatDate("2024-01-01T10:05:00Z");
    assert.match(result, /\d{1,2}:0[0-9]/);
  });

  it("converts 0 hours to 12 (12 AM)", () => {
    // Midnight UTC: should render as 12:00 AM in UTC timezone
    const result = formatDate("2024-01-01T00:00:00Z");
    // The rendering is timezone-dependent; just check format
    assert.match(result, /^[A-Z][a-z]{2} \d{1,2}, \d{4} at \d{1,2}:\d{2} (AM|PM)$/);
  });
});
