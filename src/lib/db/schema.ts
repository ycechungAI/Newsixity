import type Database from "better-sqlite3";

export function initializeSchema(db: Database.Database): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS categories (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      slug TEXT NOT NULL UNIQUE,
      sort_order INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS feeds (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      category_id INTEGER NOT NULL REFERENCES categories(id),
      name TEXT NOT NULL,
      url TEXT NOT NULL UNIQUE,
      enabled INTEGER NOT NULL DEFAULT 1,
      last_fetched_at TEXT,
      last_error TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS article_groups (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      label TEXT,
      category_id INTEGER NOT NULL REFERENCES categories(id),
      representative_id INTEGER,
      article_count INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS articles (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      feed_id INTEGER NOT NULL REFERENCES feeds(id),
      guid TEXT NOT NULL,
      title TEXT NOT NULL,
      link TEXT NOT NULL,
      author TEXT,
      published_at TEXT,
      content TEXT,
      image_url TEXT,
      summary TEXT,
      summary_model TEXT,
      is_read INTEGER NOT NULL DEFAULT 0,
      is_saved INTEGER NOT NULL DEFAULT 0,
      group_id INTEGER REFERENCES article_groups(id),
      title_hash TEXT,
      fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      UNIQUE(feed_id, guid)
    );

    CREATE TABLE IF NOT EXISTS article_research (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      article_id INTEGER NOT NULL REFERENCES articles(id),
      question TEXT NOT NULL,
      answer TEXT NOT NULL,
      sources TEXT NOT NULL DEFAULT '[]',
      model TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS search_quota (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      month_key TEXT NOT NULL UNIQUE,
      query_count INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS settings (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      key TEXT NOT NULL UNIQUE,
      value TEXT,
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS stock_watchlist (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      symbol TEXT NOT NULL UNIQUE,
      name TEXT NOT NULL,
      exchange TEXT,
      added_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS stock_quotes_cache (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      symbol TEXT NOT NULL UNIQUE,
      price REAL NOT NULL,
      change REAL NOT NULL,
      change_percent REAL NOT NULL,
      volume INTEGER,
      market_cap REAL,
      currency TEXT,
      cached_at TEXT NOT NULL DEFAULT (datetime('now')),
      expires_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS stock_charts_cache (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      symbol TEXT NOT NULL,
      timeframe TEXT NOT NULL,
      data TEXT NOT NULL,
      cached_at TEXT NOT NULL DEFAULT (datetime('now')),
      expires_at TEXT NOT NULL,
      UNIQUE(symbol, timeframe)
    );

    CREATE TABLE IF NOT EXISTS market_heatmap_snapshots (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      date TEXT NOT NULL UNIQUE,
      data TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_articles_feed_id ON articles(feed_id);
    CREATE INDEX IF NOT EXISTS idx_articles_group_id ON articles(group_id);
    CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at DESC);
    CREATE INDEX IF NOT EXISTS idx_articles_title_hash ON articles(title_hash);
    CREATE INDEX IF NOT EXISTS idx_articles_is_saved ON articles(is_saved) WHERE is_saved = 1;
    CREATE INDEX IF NOT EXISTS idx_feeds_category_id ON feeds(category_id);
    CREATE INDEX IF NOT EXISTS idx_article_groups_category_id ON article_groups(category_id);
    CREATE INDEX IF NOT EXISTS idx_article_research_article_id ON article_research(article_id);
    CREATE INDEX IF NOT EXISTS idx_stock_quotes_expires ON stock_quotes_cache(expires_at);
    CREATE INDEX IF NOT EXISTS idx_stock_charts_expires ON stock_charts_cache(expires_at);
    CREATE INDEX IF NOT EXISTS idx_heatmap_snapshots_date ON market_heatmap_snapshots(date DESC);
  `);

  // Seed default categories
  const seedCategory = db.prepare(
    `INSERT OR IGNORE INTO categories (name, slug, sort_order) VALUES (?, ?, ?)`
  );

  const seedCategories = db.transaction(() => {
    seedCategory.run("World News", "world-news", 0);
    seedCategory.run("Finance", "finance", 1);
    seedCategory.run("Gaming", "gaming", 2);
    seedCategory.run("Technology", "technology", 3);
    seedCategory.run("Sports", "sports", 4);
    seedCategory.run("Weather", "weather", 5);
    seedCategory.run("Top News", "top-news", 6);
    seedCategory.run("Others", "others", 7);
  });

  seedCategories();

  // Seed Manual Links feed for Others category
  const othersCategory = db
    .prepare("SELECT id FROM categories WHERE slug = 'others'")
    .get() as { id: number } | undefined;

  if (othersCategory) {
    db.prepare(
      "INSERT OR IGNORE INTO feeds (category_id, name, url, enabled) VALUES (?, ?, ?, ?)"
    ).run(othersCategory.id, "Manual Links", "internal://manual", 1);
  }
}
