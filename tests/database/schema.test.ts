/**
 * Database schema tests.
 *
 * Each test creates an isolated in-memory SQLite database so that the
 * real application database is never touched.
 */
import { describe, it, before, after } from "node:test";
import assert from "node:assert/strict";
import Database from "better-sqlite3";
import { initializeSchema } from "../../src/lib/db/schema.ts";

// ---------------------------------------------------------------------------
// Main test suite (single shared DB for speed)
// ---------------------------------------------------------------------------

describe("initializeSchema", () => {
  // Use proper better-sqlite3 types via dynamic import
  let db: import("better-sqlite3").Database;

  before(() => {
    db = new Database(":memory:");
    db.pragma("foreign_keys = ON");
    initializeSchema(db);
  });

  after(() => {
    db.close();
  });

  // ---- Required tables -------------------------------------------------------

  it("creates the categories table", () => {
    const tables = db
      .prepare("SELECT name FROM sqlite_master WHERE type='table'")
      .all() as { name: string }[];
    assert.ok(tables.some((t) => t.name === "categories"));
  });

  it("creates the feeds table", () => {
    const tables = db
      .prepare("SELECT name FROM sqlite_master WHERE type='table'")
      .all() as { name: string }[];
    assert.ok(tables.some((t) => t.name === "feeds"));
  });

  it("creates the articles table", () => {
    const tables = db
      .prepare("SELECT name FROM sqlite_master WHERE type='table'")
      .all() as { name: string }[];
    assert.ok(tables.some((t) => t.name === "articles"));
  });

  it("creates the article_groups table", () => {
    const tables = db
      .prepare("SELECT name FROM sqlite_master WHERE type='table'")
      .all() as { name: string }[];
    assert.ok(tables.some((t) => t.name === "article_groups"));
  });

  it("creates the settings table", () => {
    const tables = db
      .prepare("SELECT name FROM sqlite_master WHERE type='table'")
      .all() as { name: string }[];
    assert.ok(tables.some((t) => t.name === "settings"));
  });

  it("creates the stock_watchlist table", () => {
    const tables = db
      .prepare("SELECT name FROM sqlite_master WHERE type='table'")
      .all() as { name: string }[];
    assert.ok(tables.some((t) => t.name === "stock_watchlist"));
  });

  it("creates the user_preferences table", () => {
    const tables = db
      .prepare("SELECT name FROM sqlite_master WHERE type='table'")
      .all() as { name: string }[];
    assert.ok(tables.some((t) => t.name === "user_preferences"));
  });

  // ---- Seeded default categories ---------------------------------------------

  it("seeds default categories", () => {
    const rows = db.prepare("SELECT slug FROM categories ORDER BY sort_order").all() as {
      slug: string;
    }[];
    const slugs = rows.map((r) => r.slug);
    assert.ok(slugs.includes("world-news"));
    assert.ok(slugs.includes("finance"));
    assert.ok(slugs.includes("technology"));
    assert.ok(slugs.includes("others"));
  });

  it("seeds exactly 8 default categories", () => {
    const count = (
      db.prepare("SELECT COUNT(*) AS n FROM categories").get() as { n: number }
    ).n;
    assert.equal(count, 8);
  });

  it("seeds a Manual Links feed in the 'others' category", () => {
    const feed = db
      .prepare(
        `SELECT f.name, f.url
         FROM feeds f
         JOIN categories c ON f.category_id = c.id
         WHERE c.slug = 'others' AND f.name = 'Manual Links'`
      )
      .get() as { name: string; url: string } | undefined;
    assert.ok(feed, "Manual Links feed should exist");
    assert.equal(feed.url, "internal://manual");
  });

  // ---- Migrations: extra columns on existing DB ------------------------------

  it("adds relevance_score column to articles if missing (idempotent)", () => {
    const cols = db.prepare("PRAGMA table_info(articles)").all() as {
      name: string;
    }[];
    assert.ok(cols.some((c) => c.name === "relevance_score"));
  });

  it("adds is_promoted column to articles if missing (idempotent)", () => {
    const cols = db.prepare("PRAGMA table_info(articles)").all() as {
      name: string;
    }[];
    assert.ok(cols.some((c) => c.name === "is_promoted"));
  });

  it("adds source_weight column to feeds if missing (idempotent)", () => {
    const cols = db.prepare("PRAGMA table_info(feeds)").all() as {
      name: string;
    }[];
    assert.ok(cols.some((c) => c.name === "source_weight"));
  });

  it("is idempotent: calling initializeSchema twice does not throw", () => {
    assert.doesNotThrow(() => initializeSchema(db));
  });
});
