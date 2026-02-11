import Parser from "rss-parser";
import { ParsedArticle } from "@/types";
import { getDb } from "@/lib/db";

type CustomFeed = {};
type CustomItem = {
  "media:content"?: { $: { url?: string } };
  "media:thumbnail"?: { $: { url?: string } };
};

const parser = new Parser<CustomFeed, CustomItem>({
  timeout: 15000,
  headers: {
    "User-Agent": "Newsixity/1.0",
  },
  customFields: {
    item: [
      ["media:content", "media:content"],
      ["media:thumbnail", "media:thumbnail"],
    ],
  },
});

function stripHtml(html: string): string {
  return html
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/\s+/g, " ")
    .trim();
}

function extractImageFromHtml(html: string): string | null {
  const match = html.match(/<img[^>]+src=["']([^"']+)["']/i);
  return match ? match[1] : null;
}

export async function fetchFeed(url: string): Promise<ParsedArticle[]> {
  const feed = await parser.parseURL(url);

  return (feed.items || []).map((item) => {
    const guid = item.guid || item.link || item.title || "";

    const title = (item.title || "").trim();

    const link = item.link || "";

    const author = item.creator || (item as any).author || null;

    const publishedAt = new Date(
      item.pubDate || item.isoDate || Date.now()
    ).toISOString();

    // Extract content
    let content: string | null = null;
    if (item.contentSnippet) {
      content = item.contentSnippet.substring(0, 5000);
    } else if (item.content) {
      content = stripHtml(item.content).substring(0, 5000);
    }

    // Extract image URL with fallback chain
    let imageUrl: string | null = null;

    if (item.enclosure?.url) {
      imageUrl = item.enclosure.url;
    } else if (item["media:content"]?.$?.url) {
      imageUrl = item["media:content"].$.url;
    } else if (item["media:thumbnail"]?.$?.url) {
      imageUrl = item["media:thumbnail"].$.url;
    } else if (item.content) {
      imageUrl = extractImageFromHtml(item.content);
    }

    return {
      guid,
      title,
      link,
      author,
      publishedAt,
      content,
      imageUrl,
    };
  });
}

interface FeedRow {
  id: number;
  url: string;
  enabled: number;
}

interface FeedResult {
  feedId: number;
  feedUrl: string;
  articles: ParsedArticle[];
  error?: string;
}

export async function fetchAllFeeds(): Promise<FeedResult[]> {
  const db = getDb();

  const allFeeds = db
    .prepare(`SELECT id, url, enabled FROM feeds WHERE enabled = 1`)
    .all() as FeedRow[];

  const updateLastFetched = db.prepare(
    `UPDATE feeds SET last_fetched_at = datetime('now'), last_error = NULL WHERE id = ?`
  );

  const updateLastError = db.prepare(
    `UPDATE feeds SET last_error = ? WHERE id = ?`
  );

  const results: FeedResult[] = [];
  const concurrencyLimit = 5;

  // Process feeds in batches of concurrencyLimit
  for (let i = 0; i < allFeeds.length; i += concurrencyLimit) {
    const batch = allFeeds.slice(i, i + concurrencyLimit);

    const batchResults = await Promise.allSettled(
      batch.map(async (feed) => {
        const articles = await fetchFeed(feed.url);
        return { feedId: feed.id, feedUrl: feed.url, articles };
      })
    );

    for (let j = 0; j < batchResults.length; j++) {
      const result = batchResults[j];
      const feed = batch[j];

      if (result.status === "fulfilled") {
        updateLastFetched.run(feed.id);
        results.push(result.value);
      } else {
        const errorMessage =
          result.reason instanceof Error
            ? result.reason.message
            : String(result.reason);
        updateLastError.run(errorMessage, feed.id);
        results.push({
          feedId: feed.id,
          feedUrl: feed.url,
          articles: [],
          error: errorMessage,
        });
      }
    }
  }

  return results;
}
