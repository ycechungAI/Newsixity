export function parseHttpUrl(value: string | null | undefined): URL | null {
  if (!value) return null;
  const normalized = value.trim();
  if (!normalized) return null;

  try {
    const parsed = new URL(normalized);
    const protocol = parsed.protocol.toLowerCase();
    if (protocol !== "http:" && protocol !== "https:") {
      return null;
    }

    // Disallow credential-bearing URLs.
    if (parsed.username || parsed.password) {
      return null;
    }

    return parsed;
  } catch {
    return null;
  }
}

export function isHttpUrl(value: string | null | undefined): boolean {
  return parseHttpUrl(value) !== null;
}
