"""Port of src/lib/utils/url.ts — SSRF/credential-URL hardening.

Only http(s) URLs without embedded credentials are considered safe to store
or fetch. This guards the same surfaces the Node app hardened per
docs/migration/todo.md legacy item #3 (SSRF protections for server-side
fetches of manual links / article content).
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


def parse_http_url(value: str | None) -> str | None:
    """Return a normalized http(s) URL string, or None if unsafe/invalid."""
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None

    try:
        parsed = urlsplit(normalized)
    except ValueError:
        return None

    if parsed.scheme.lower() not in ("http", "https"):
        return None

    # Disallow credential-bearing URLs (user:pass@host).
    if parsed.username or parsed.password:
        return None

    if not parsed.netloc:
        return None

    return urlunsplit(parsed)


def is_http_url(value: str | None) -> bool:
    return parse_http_url(value) is not None
