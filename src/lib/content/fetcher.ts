/**
 * Fetches article text content from the original URL when RSS content is empty.
 * Tries a simple HTTP fetch first, then falls back to headless Chromium for
 * JS-rendered sites (e.g. Yahoo Finance).
 */
import { lookup } from "dns/promises";
import net from "net";
import { parseHttpUrl } from "@/lib/utils/url";

const FETCH_TIMEOUT = 10000;
const BROWSER_TIMEOUT = 30000;
const BLOCKED_HOSTNAMES = new Set([
  "localhost",
  "127.0.0.1",
  "::1",
  "0.0.0.0",
  "host.docker.internal",
  "metadata.google.internal",
]);

function isPrivateIpv4(address: string): boolean {
  const parts = address.split(".").map((p) => Number.parseInt(p, 10));
  if (parts.length !== 4 || parts.some((p) => Number.isNaN(p) || p < 0 || p > 255)) {
    return false;
  }

  const [a, b] = parts;
  if (a === 10) return true;
  if (a === 127) return true;
  if (a === 169 && b === 254) return true;
  if (a === 172 && b >= 16 && b <= 31) return true;
  if (a === 192 && b === 168) return true;
  if (a === 0) return true;
  return false;
}

function isPrivateIpv6(address: string): boolean {
  const value = address.toLowerCase();
  if (value === "::1" || value === "0:0:0:0:0:0:0:1") return true;
  if (value.startsWith("fe80:")) return true; // link-local
  if (value.startsWith("fc") || value.startsWith("fd")) return true; // ULA

  if (value.startsWith("::ffff:")) {
    const mapped = value.slice("::ffff:".length);
    return isPrivateIpv4(mapped);
  }

  return false;
}

function isBlockedIp(address: string): boolean {
  const ipType = net.isIP(address);
  if (ipType === 4) return isPrivateIpv4(address);
  if (ipType === 6) return isPrivateIpv6(address);
  return true;
}

async function resolvesToBlockedIp(hostname: string): Promise<boolean> {
  const normalized = hostname.trim().toLowerCase();
  if (!normalized) return true;
  if (BLOCKED_HOSTNAMES.has(normalized)) return true;

  if (net.isIP(normalized) !== 0) {
    return isBlockedIp(normalized);
  }

  try {
    const addresses = await lookup(normalized, { all: true, verbatim: true });
    if (addresses.length === 0) return true;
    return addresses.some(({ address }) => isBlockedIp(address));
  } catch {
    // Fail closed for network target validation.
    return true;
  }
}

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
  const parsedUrl = parseHttpUrl(url);
  if (!parsedUrl) {
    console.warn(`[Newsixity] Skipping non-http URL during content fetch: ${url}`);
    return null;
  }

  if (await resolvesToBlockedIp(parsedUrl.hostname)) {
    console.warn(`[Newsixity] Blocked potential SSRF target: ${parsedUrl.hostname}`);
    return null;
  }

  const safeUrl = parsedUrl.toString();

  // For known JS-heavy sites, go straight to browser
  if (needsBrowser(safeUrl)) {
    console.log(`[Newsixity] Using browser fetch for JS-heavy site: ${safeUrl}`);
    const html = await fetchWithBrowser(safeUrl);
    if (html) {
      const text = extractArticleText(html);
      if (text && text.length > 100) return text;
    }
    return null;
  }

  // Try simple HTTP fetch first
  const html = await fetchWithHttp(safeUrl);
  if (html) {
    const text = extractArticleText(html);
    if (text && text.length > 100) return text;
  }

  // Fallback to browser if simple fetch got no useful content
  console.log(`[Newsixity] Simple fetch got no content, trying browser for: ${safeUrl}`);
  const browserHtml = await fetchWithBrowser(safeUrl);
  if (browserHtml) {
    const text = extractArticleText(browserHtml);
    if (text && text.length > 100) return text;
  }

  return null;
}
