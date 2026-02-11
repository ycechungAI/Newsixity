/**
 * Fetches article text content from the original URL when RSS content is empty.
 * Tries a simple HTTP fetch first, then falls back to headless Chromium for
 * JS-rendered sites (e.g. Yahoo Finance).
 */

const FETCH_TIMEOUT = 10000;
const BROWSER_TIMEOUT = 30000;

function stripHtmlTags(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<nav[\s\S]*?<\/nav>/gi, "")
    .replace(/<header[\s\S]*?<\/header>/gi, "")
    .replace(/<footer[\s\S]*?<\/footer>/gi, "")
    .replace(/<aside[\s\S]*?<\/aside>/gi, "")
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/&#x27;/gi, "'")
    .replace(/&#x2F;/gi, "/")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Try to extract the main article content from an HTML page.
 * Looks for common article container patterns.
 */
function extractArticleText(html: string): string | null {
  // Try to find article body using common patterns
  const patterns = [
    /<article[^>]*>([\s\S]*?)<\/article>/i,
    /<div[^>]*class="[^"]*article[_-]?body[^"]*"[^>]*>([\s\S]*?)<\/div>/i,
    /<div[^>]*class="[^"]*caas-body[^"]*"[^>]*>([\s\S]*?)<\/div>/i,
    /<div[^>]*class="[^"]*story[_-]?body[^"]*"[^>]*>([\s\S]*?)<\/div>/i,
    /<div[^>]*class="[^"]*entry[_-]?content[^"]*"[^>]*>([\s\S]*?)<\/div>/i,
    /<div[^>]*class="[^"]*post[_-]?content[^"]*"[^>]*>([\s\S]*?)<\/div>/i,
    /<div[^>]*class="[^"]*content[_-]?body[^"]*"[^>]*>([\s\S]*?)<\/div>/i,
    /<main[^>]*>([\s\S]*?)<\/main>/i,
  ];

  for (const pattern of patterns) {
    const match = html.match(pattern);
    if (match) {
      const text = stripHtmlTags(match[1]);
      if (text.length > 100) {
        return text.substring(0, 8000);
      }
    }
  }

  // Fallback: collect all <p> tag contents
  const paragraphs: string[] = [];
  const pRegex = /<p[^>]*>([\s\S]*?)<\/p>/gi;
  let pMatch;
  while ((pMatch = pRegex.exec(html)) !== null) {
    const text = stripHtmlTags(pMatch[1]).trim();
    if (text.length > 30) {
      paragraphs.push(text);
    }
  }

  if (paragraphs.length > 0) {
    const combined = paragraphs.join("\n\n");
    if (combined.length > 100) {
      return combined.substring(0, 8000);
    }
  }

  return null;
}

/** Domains known to require JS rendering */
const JS_REQUIRED_DOMAINS = [
  "finance.yahoo.com",
  "yahoo.com",
  "bloomberg.com",
  "wsj.com",
  "ft.com",
];

function needsBrowser(url: string): boolean {
  try {
    const hostname = new URL(url).hostname;
    return JS_REQUIRED_DOMAINS.some(
      (d) => hostname === d || hostname.endsWith("." + d)
    );
  } catch {
    return false;
  }
}

/**
 * Fetch HTML using headless Chromium via Playwright.
 * Returns the rendered page HTML, or null on failure.
 */
async function fetchWithBrowser(url: string): Promise<string | null> {
  let browser;
  try {
    const { chromium } = await import("playwright-core");
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      userAgent:
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    });
    const page = await context.newPage();

    await page.goto(url, {
      waitUntil: "domcontentloaded",
      timeout: BROWSER_TIMEOUT,
    });

    // Wait for JS to render article content
    await page.waitForTimeout(4000);

    // Try to dismiss consent/cookie banners by clicking common buttons
    try {
      const consentSelectors = [
        'button[name="agree"]',
        'button:has-text("Accept")',
        'button:has-text("Accept All")',
        'button:has-text("I agree")',
        'button:has-text("Consent")',
        'button:has-text("OK")',
        ".consent-overlay button",
        "#consent-page button",
      ];
      for (const sel of consentSelectors) {
        const btn = page.locator(sel).first();
        if (await btn.isVisible({ timeout: 500 }).catch(() => false)) {
          await btn.click();
          await page.waitForTimeout(1500);
          break;
        }
      }
    } catch {
      // Consent dismissal is best-effort
    }

    const html = await page.content();
    await browser.close();
    return html;
  } catch (e) {
    console.warn(
      `[Newsixity] Browser fetch failed for ${url}: ${e instanceof Error ? e.message : String(e)}`
    );
    if (browser) await browser.close().catch(() => {});
    return null;
  }
}

/**
 * Simple HTTP fetch for static sites.
 */
async function fetchWithHttp(url: string): Promise<string | null> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT);

    const response = await fetch(url, {
      signal: controller.signal,
      headers: {
        "User-Agent":
          "Mozilla/5.0 (compatible; Newsixity/1.0; +https://newsixity.app)",
        Accept: "text/html,application/xhtml+xml",
      },
      redirect: "follow",
    });

    clearTimeout(timeout);

    if (!response.ok) return null;

    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("text/html") && !contentType.includes("xhtml")) {
      return null;
    }

    return await response.text();
  } catch {
    return null;
  }
}

/**
 * Fetch and extract article text from a URL.
 * Tries simple HTTP first, falls back to headless browser for JS-heavy sites.
 */
export async function fetchArticleContent(url: string): Promise<string | null> {
  // For known JS-heavy sites, go straight to browser
  if (needsBrowser(url)) {
    console.log(`[Newsixity] Using browser fetch for JS-heavy site: ${url}`);
    const html = await fetchWithBrowser(url);
    if (html) {
      const text = extractArticleText(html);
      if (text && text.length > 100) return text;
    }
    return null;
  }

  // Try simple HTTP fetch first
  const html = await fetchWithHttp(url);
  if (html) {
    const text = extractArticleText(html);
    if (text && text.length > 100) return text;
  }

  // Fallback to browser if simple fetch got no useful content
  console.log(`[Newsixity] Simple fetch got no content, trying browser for: ${url}`);
  const browserHtml = await fetchWithBrowser(url);
  if (browserHtml) {
    const text = extractArticleText(browserHtml);
    if (text && text.length > 100) return text;
  }

  return null;
}
