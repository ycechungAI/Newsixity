/**
 * Database CRUD tests.
 *
 * Uses an isolated in-memory SQLite database (never touches the real DB).
 * Tests verify that the schema enforces expected constraints and that
 * common read/write patterns work correctly.
 */
import { describe, it, before, after } from "node:test";
import assert from "node:assert/strict";
import Database from "better-sqlite3";
import { initializeSchema } from "../../src/lib/db/schema.ts";

// ---------------------------------------------------------------------------
// Shared DB setup
// ---------------------------------------------------------------------------

let db: import("better-sqlite3").Database;

before(() => {
  db = new Database(":memory:");
  db.pragma("foreign_keys = ON");
  initializeSchema(db);
});

after(() => {
  db.close();
});

// ---------------------------------------------------------------------------
// Categories
// ---------------------------------------------------------------------------

describe("categories table", () => {
  it("enforces UNIQUE constraint on name", () => {
    assert.throws(() => {
      db.prepare(
        "INSERT INTO categories (name, slug, sort_order) VALUES (?, ?, ?)"
      ).run("World News", "world-news-dupe", 99);
    }, /UNIQUE constraint failed/);
  });

  it("enforces UNIQUE constraint on slug", () => {
    assert.throws(() => {
      db.prepare(
        "INSERT INTO categories (name, slug, sort_order) VALUES (?, ?, ?)"
      ).run("World News Dupe", "world-news", 99);
    }, /UNIQUE constraint failed/);
  });

  it("inserts a new category successfully", () => {
    db.prepare(
      "INSERT INTO categories (name, slug, sort_order) VALUES (?, ?, ?)"
    ).run("Test Category", "test-category", 99);

    const row = db
      .prepare("SELECT * FROM categories WHERE slug = ?")
      .get("test-category") as { name: string; slug: string } | undefined;

    assert.ok(row);
    assert.equal(row.name, "Test Category");
  });

  it("retrieves categories ordered by sort_order", () => {
    const rows = db
      .prepare("SELECT slug FROM categories ORDER BY sort_order")
      .all() as { slug: string }[];
    // First seeded category is world-news (sort_order 0)
    assert.equal(rows[0].slug, "world-news");
  });
});

// ---------------------------------------------------------------------------
// Feeds
// ---------------------------------------------------------------------------

describe("feeds table", () => {
  let categoryId: number;

  before(() => {
    const cat = db
      .prepare("SELECT id FROM categories WHERE slug = ?")
      .get("technology") as { id: number };
    categoryId = cat.id;
  });

  it("inserts a feed referencing a valid category", () => {
    db.prepare(
      "INSERT INTO feeds (category_id, name, url) VALUES (?, ?, ?)"
    ).run(categoryId, "Test Feed", "https://example.com/rss.xml");

    const row = db
      .prepare("SELECT * FROM feeds WHERE url = ?")
      .get("https://example.com/rss.xml") as { name: string } | undefined;

    assert.ok(row);
    assert.equal(row.name, "Test Feed");
  });

  it("enforces UNIQUE constraint on url", () => {
    assert.throws(() => {
      db.prepare(
        "INSERT INTO feeds (category_id, name, url) VALUES (?, ?, ?)"
      ).run(categoryId, "Duplicate Feed", "https://example.com/rss.xml");
    }, /UNIQUE constraint failed/);
  });

  it("enforces foreign key: rejects invalid category_id", () => {
    assert.throws(() => {
      db.prepare(
        "INSERT INTO feeds (category_id, name, url) VALUES (?, ?, ?)"
      ).run(99999, "Orphan Feed", "https://orphan.com/rss.xml");
    }, /FOREIGN KEY constraint failed/);
  });

  it("defaults enabled to 1", () => {
    db.prepare(
      "INSERT INTO feeds (category_id, name, url) VALUES (?, ?, ?)"
    ).run(categoryId, "Default Enabled Feed", "https://default-enabled.com/rss.xml");

    const row = db
      .prepare("SELECT enabled FROM feeds WHERE url = ?")
      .get("https://default-enabled.com/rss.xml") as { enabled: number };
    assert.equal(row.enabled, 1);
  });
});

// ---------------------------------------------------------------------------
// Articles
// ---------------------------------------------------------------------------

describe("articles table", () => {
  let feedId: number;

  before(() => {
    const cat = db
      .prepare("SELECT id FROM categories WHERE slug = ?")
      .get("finance") as { id: number };

    db.prepare(
      "INSERT OR IGNORE INTO feeds (category_id, name, url) VALUES (?, ?, ?)"
    ).run(cat.id, "Finance Test Feed", "https://finance-test.com/rss.xml");

    const feed = db
      .prepare("SELECT id FROM feeds WHERE url = ?")
      .get("https://finance-test.com/rss.xml") as { id: number };
    feedId = feed.id;
  });

  it("inserts an article successfully", () => {
    db.prepare(
      `INSERT INTO articles (feed_id, guid, title, link)
       VALUES (?, ?, ?, ?)`
    ).run(feedId, "guid-001", "Test Article Title", "https://example.com/article/1");

    const row = db
      .prepare("SELECT * FROM articles WHERE guid = ?")
      .get("guid-001") as { title: string; is_read: number; is_saved: number } | undefined;

    assert.ok(row);
    assert.equal(row.title, "Test Article Title");
  });

  it("defaults is_read to 0", () => {
    const row = db
      .prepare("SELECT is_read FROM articles WHERE guid = ?")
      .get("guid-001") as { is_read: number };
    assert.equal(row.is_read, 0);
  });

  it("defaults is_saved to 0", () => {
    const row = db
      .prepare("SELECT is_saved FROM articles WHERE guid = ?")
      .get("guid-001") as { is_saved: number };
    assert.equal(row.is_saved, 0);
  });

  it("enforces UNIQUE(feed_id, guid) constraint", () => {
    assert.throws(() => {
      db.prepare(
        `INSERT INTO articles (feed_id, guid, title, link)
         VALUES (?, ?, ?, ?)`
      ).run(feedId, "guid-001", "Duplicate", "https://example.com/article/dup");
    }, /UNIQUE constraint failed/);
  });

  it("allows same guid across different feeds", () => {
    const cat = db
      .prepare("SELECT id FROM categories WHERE slug = ?")
      .get("gaming") as { id: number };

    db.prepare(
      "INSERT OR IGNORE INTO feeds (category_id, name, url) VALUES (?, ?, ?)"
    ).run(cat.id, "Gaming Feed", "https://gaming-test.com/rss.xml");

    const otherFeed = db
      .prepare("SELECT id FROM feeds WHERE url = ?")
      .get("https://gaming-test.com/rss.xml") as { id: number };

    assert.doesNotThrow(() => {
      db.prepare(
        `INSERT INTO articles (feed_id, guid, title, link)
         VALUES (?, ?, ?, ?)`
      ).run(otherFeed.id, "guid-001", "Same GUID Different Feed", "https://gaming.com/1");
    });
  });

  it("enforces foreign key: rejects invalid feed_id", () => {
    assert.throws(() => {
      db.prepare(
        `INSERT INTO articles (feed_id, guid, title, link)
         VALUES (?, ?, ?, ?)`
      ).run(99999, "guid-orphan", "Orphan Article", "https://orphan.com/1");
    }, /FOREIGN KEY constraint failed/);
  });

  it("can mark an article as read", () => {
    db.prepare("UPDATE articles SET is_read = 1 WHERE guid = ?").run("guid-001");
    const row = db
      .prepare("SELECT is_read FROM articles WHERE guid = ? AND feed_id = ?")
      .get("guid-001", feedId) as { is_read: number };
    assert.equal(row.is_read, 1);
  });

  it("can mark an article as saved", () => {
    db.prepare("UPDATE articles SET is_saved = 1 WHERE guid = ?").run("guid-001");
    const row = db
      .prepare("SELECT is_saved FROM articles WHERE guid = ? AND feed_id = ?")
      .get("guid-001", feedId) as { is_saved: number };
    assert.equal(row.is_saved, 1);
  });
});

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

describe("settings table", () => {
  it("inserts a key-value pair", () => {
    db.prepare(
      "INSERT INTO settings (key, value) VALUES (?, ?)"
    ).run("theme", "dark");

    const row = db
      .prepare("SELECT value FROM settings WHERE key = ?")
      .get("theme") as { value: string } | undefined;
    assert.ok(row);
    assert.equal(row.value, "dark");
  });

  it("enforces UNIQUE constraint on key", () => {
    assert.throws(() => {
      db.prepare(
        "INSERT INTO settings (key, value) VALUES (?, ?)"
      ).run("theme", "light");
    }, /UNIQUE constraint failed/);
  });

  it("updates an existing setting using INSERT OR REPLACE", () => {
    db.prepare(
      "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)"
    ).run("theme", "light");

    const row = db
      .prepare("SELECT value FROM settings WHERE key = ?")
      .get("theme") as { value: string };
    assert.equal(row.value, "light");
  });
});

// ---------------------------------------------------------------------------
// Stock watchlist
// ---------------------------------------------------------------------------

describe("stock_watchlist table", () => {
  it("inserts a stock symbol", () => {
    db.prepare(
      "INSERT INTO stock_watchlist (symbol, name) VALUES (?, ?)"
    ).run("AAPL", "Apple Inc.");

    const row = db
      .prepare("SELECT * FROM stock_watchlist WHERE symbol = ?")
      .get("AAPL") as { name: string } | undefined;
    assert.ok(row);
    assert.equal(row.name, "Apple Inc.");
  });

  it("enforces UNIQUE constraint on symbol", () => {
    assert.throws(() => {
      db.prepare(
        "INSERT INTO stock_watchlist (symbol, name) VALUES (?, ?)"
      ).run("AAPL", "Apple Inc. Duplicate");
    }, /UNIQUE constraint failed/);
  });

  it("allows deleting a symbol from the watchlist", () => {
    db.prepare("DELETE FROM stock_watchlist WHERE symbol = ?").run("AAPL");
    const row = db
      .prepare("SELECT * FROM stock_watchlist WHERE symbol = ?")
      .get("AAPL");
    assert.equal(row, undefined);
  });
});

// ---------------------------------------------------------------------------
// User preferences
// ---------------------------------------------------------------------------

describe("user_preferences table", () => {
  it("inserts a preference", () => {
    db.prepare(
      `INSERT INTO user_preferences (category_slug, keyword, weight, source)
       VALUES (?, ?, ?, ?)`
    ).run("technology", "ai", 2.5, "manual");

    const row = db
      .prepare(
        "SELECT * FROM user_preferences WHERE category_slug = ? AND keyword = ?"
      )
      .get("technology", "ai") as { weight: number; source: string } | undefined;
    assert.ok(row);
    assert.equal(row.weight, 2.5);
    assert.equal(row.source, "manual");
  });

  it("enforces UNIQUE(category_slug, keyword)", () => {
    assert.throws(() => {
      db.prepare(
        `INSERT INTO user_preferences (category_slug, keyword, weight, source)
         VALUES (?, ?, ?, ?)`
      ).run("technology", "ai", 1.0, "auto");
    }, /UNIQUE constraint failed/);
  });

  it("allows same keyword in different categories", () => {
    assert.doesNotThrow(() => {
      db.prepare(
        `INSERT INTO user_preferences (category_slug, keyword, weight, source)
         VALUES (?, ?, ?, ?)`
      ).run("finance", "ai", 1.0, "auto");
    });
  });
});
