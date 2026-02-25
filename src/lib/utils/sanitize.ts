export function stripHtml(html: string): string {
  let text = html.replace(/<[^>]*>/g, "");

  text = text
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");

  text = text.replace(/\s+/g, " ").trim();

  return text;
}

export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;

  const truncated = text.slice(0, maxLength);
  const lastSpace = truncated.lastIndexOf(" ");

  if (lastSpace > maxLength * 0.8) {
    return truncated.slice(0, lastSpace) + "...";
  }

  return truncated + "...";
}

export function extractImageFromHtml(html: string): string | null {
  const match = html.match(/<img\s[^>]*src=["']([^"']+)["']/i);
  return match ? match[1] : null;
}
