"""HTTP-only content extraction — port of src/lib/content/fetcher.ts without Playwright.

Uses trafilatura for content extraction, falling back to pattern-based extraction
if trafilatura is unavailable. Includes SSRF protection (IP-based blocking).
"""

import re
import socket
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.lib.utils.sanitize import MAX_CONTENT_LENGTH
from app.lib.utils.url import parse_http_url

FETCH_TIMEOUT = 10.0
BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "host.docker.internal",
    "metadata.google.internal",
}


def is_private_ipv4(addr: str) -> bool:
    """Check if IPv4 address is in private range."""
    try:
        ip = IPv4Address(addr)
        return ip.is_private or ip.is_loopback
    except Exception:
        return False


def is_private_ipv6(addr: str) -> bool:
    """Check if IPv6 address is in private range."""
    try:
        ip = IPv6Address(addr)
        return ip.is_private or ip.is_loopback
    except Exception:
        return False


def is_blocked_ip(address: str) -> bool:
    """Check if IP address should be blocked (private/loopback)."""
    try:
        ip = ip_address(address)
        return ip.is_private or ip.is_loopback
    except Exception:
        return True


def resolves_to_blocked_ip(hostname: str) -> bool:
    """Check if hostname is blocked or resolves to private IP."""
    normalized = hostname.strip().lower()

    if not normalized:
        return True

    if normalized in BLOCKED_HOSTNAMES:
        return True

    # If it's already an IP literal, check it directly rather than resolving.
    try:
        ip_address(normalized)
    except ValueError:
        pass
    else:
        return is_blocked_ip(normalized)

    # Try DNS resolution
    try:
        addresses = socket.getaddrinfo(normalized, None)
        if not addresses:
            return True
        for addr_info in addresses:
            resolved_ip = addr_info[4][0]
            if is_blocked_ip(resolved_ip):
                return True
        return False
    except socket.gaierror:
        # Fail closed on DNS lookup failure
        return True


def strip_html_tags(html: str) -> str:
    """Remove HTML tags and decode entities."""
    # Remove script/style/nav/header/footer/aside
    html = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"<nav[\s\S]*?</nav>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"<header[\s\S]*?</header>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"<footer[\s\S]*?</footer>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"<aside[\s\S]*?</aside>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"<!--[\s\S]*?-->", "", html)

    # Remove tags
    html = re.sub(r"<[^>]+>", " ", html)

    # Decode entities
    html = html.replace("&nbsp;", " ")
    html = html.replace("&amp;", "&")
    html = html.replace("&lt;", "<")
    html = html.replace("&gt;", ">")
    html = html.replace("&quot;", '"')
    html = html.replace("&#39;", "'")
    html = html.replace("&#x27;", "'")
    html = html.replace("&#x2F;", "/")

    # Normalize whitespace
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def extract_article_text_fallback(html: str) -> Optional[str]:
    """Fallback content extraction using pattern matching."""
    patterns = [
        r"<article[^>]*>([\s\S]*?)</article>",
        r'<div[^>]*class="[^"]*article[_-]?body[^"]*"[^>]*>([\s\S]*?)</div>',
        r'<div[^>]*class="[^"]*caas-body[^"]*"[^>]*>([\s\S]*?)</div>',
        r'<div[^>]*class="[^"]*story[_-]?body[^"]*"[^>]*>([\s\S]*?)</div>',
        r'<div[^>]*class="[^"]*entry[_-]?content[^"]*"[^>]*>([\s\S]*?)</div>',
        r'<div[^>]*class="[^"]*post[_-]?content[^"]*"[^>]*>([\s\S]*?)</div>',
        r'<div[^>]*class="[^"]*content[_-]?body[^"]*"[^>]*>([\s\S]*?)</div>',
        r"<main[^>]*>([\s\S]*?)</main>",
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            text = strip_html_tags(match.group(1))
            if len(text) > 100:
                return text[:MAX_CONTENT_LENGTH]

    # Fallback: collect <p> tags
    paragraphs = []
    for match in re.finditer(r"<p[^>]*>([\s\S]*?)</p>", html, re.IGNORECASE):
        text = strip_html_tags(match.group(1)).strip()
        if len(text) > 30:
            paragraphs.append(text)

    if paragraphs:
        combined = "\n\n".join(paragraphs)
        if len(combined) > 100:
            return combined[:MAX_CONTENT_LENGTH]

    return None


async def fetch_article_content(url: str) -> Optional[str]:
    """Fetch and extract article text from URL (HTTP-only, no browser)."""
    safe_url = parse_http_url(url)
    if not safe_url:
        return None

    if resolves_to_blocked_ip(urlparse(safe_url).hostname):
        return None

    try:
        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT) as client:
            response = await client.get(
                safe_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; Newsixity/1.0; +https://newsixity.app)",
                    "Accept": "text/html,application/xhtml+xml",
                },
                follow_redirects=True,
            )

            if response.status_code != 200:
                return None

            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "xhtml" not in content_type:
                return None

            html = response.text

            # Try trafilatura first if available
            try:
                import trafilatura

                extracted = trafilatura.extract(html, include_comments=False)
                if extracted and len(extracted) > 100:
                    return extracted[:MAX_CONTENT_LENGTH]
            except ImportError:
                pass

            # Fallback to pattern-based extraction
            text = extract_article_text_fallback(html)
            if text and len(text) > 100:
                return text

            return None

    except Exception:
        return None
