import { FeedConfig } from "@/types";
import { getDb } from "@/lib/db";

export const DEFAULT_FEEDS: Record<string, FeedConfig[]> = {
  "world-news": [
    { name: "Reuters - World", url: "https://feeds.reuters.com/Reuters/worldNews" },
    { name: "BBC News - World", url: "https://feeds.bbci.co.uk/news/world/rss.xml" },
    { name: "BBC News - Top Stories", url: "https://feeds.bbci.co.uk/news/rss.xml" },
    { name: "NPR News", url: "https://feeds.npr.org/1001/rss.xml" },
    { name: "Al Jazeera", url: "https://www.aljazeera.com/xml/rss/all.xml" },
    { name: "Associated Press", url: "https://rsshub.app/apnews/topics/apf-topnews" },
  ],
  finance: [
    { name: "MarketWatch - Top Stories", url: "https://feeds.marketwatch.com/marketwatch/topstories" },
    { name: "CNBC Top News", url: "https://www.cnbc.com/id/100003114/device/rss/rss.html" },
    { name: "Yahoo Finance", url: "https://finance.yahoo.com/news/rssindex" },
    { name: "Financial Times", url: "https://www.ft.com/rss/home" },
    { name: "Bloomberg", url: "https://feeds.bloomberg.com/markets/news.rss" },
  ],
  gaming: [
    { name: "IGN", url: "https://feeds.feedburner.com/ign/all" },
    { name: "Kotaku", url: "https://kotaku.com/rss" },
    { name: "PC Gamer", url: "https://www.pcgamer.com/rss/" },
    { name: "Eurogamer", url: "https://www.eurogamer.net/feed" },
    { name: "Rock Paper Shotgun", url: "https://www.rockpapershotgun.com/feed" },
  ],
  technology: [
    { name: "TechCrunch", url: "https://techcrunch.com/feed/" },
    { name: "The Verge", url: "https://www.theverge.com/rss/index.xml" },
    { name: "Ars Technica", url: "https://feeds.arstechnica.com/arstechnica/index" },
    { name: "Wired", url: "https://www.wired.com/feed/rss" },
    { name: "Hacker News", url: "https://hnrss.org/frontpage" },
  ],
  sports: [
    { name: "ESPN - Top Headlines", url: "https://www.espn.com/espn/rss/news" },
    { name: "BBC Sport", url: "https://feeds.bbci.co.uk/sport/rss.xml" },
    { name: "CBS Sports", url: "https://www.cbssports.com/rss/headlines/" },
    { name: "Bleacher Report", url: "https://bleacherreport.com/articles/feed" },
  ],
  weather: [
    { name: "Weather.gov Alerts", url: "https://alerts.weather.gov/cap/us.php?x=1" },
    { name: "Weather Underground", url: "https://www.wunderground.com/rss/news.xml" },
    { name: "AccuWeather", url: "https://rss.accuweather.com/rss/liveweather_rss.asp?locCode=us" },
    { name: "Weather.com", url: "https://weather.com/feeds/enhancedweather" },
  ],
  "top-news": [
    { name: "AP News - US", url: "https://rsshub.app/apnews/topics/apf-usnews" },
    { name: "Reuters - Top News", url: "https://feeds.reuters.com/reuters/topNews" },
    { name: "CNN - Top Stories", url: "https://rss.cnn.com/rss/edition.rss" },
    { name: "Google News", url: "https://news.google.com/rss" },
  ],
};

export async function seedAllFeeds(): Promise<void> {
  const db = getDb();

  const getCategoryId = db.prepare(
    `SELECT id FROM categories WHERE slug = ?`
  );

  const insertFeed = db.prepare(
    `INSERT OR IGNORE INTO feeds (category_id, name, url) VALUES (?, ?, ?)`
  );

  const seedTransaction = db.transaction(() => {
    for (const [slug, feeds] of Object.entries(DEFAULT_FEEDS)) {
      const category = getCategoryId.get(slug) as { id: number } | undefined;
      if (!category) {
        console.warn(`Category "${slug}" not found, skipping feeds`);
        continue;
      }

      for (const feed of feeds) {
        insertFeed.run(category.id, feed.name, feed.url);
      }
    }
  });

  seedTransaction();
}
