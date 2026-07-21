"""Port of src/lib/utils/sanitize.ts. Used to strip HTML from untrusted
RSS/article content before storage — part of the app's stored-XSS hardening
(see docs/migration/todo.md legacy item #2)."""

from __future__ import annotations

import re

_TAG_RE = re.compile(r"<[^>]*>")
_WS_RE = re.compile(r"\s+")


def strip_html(html: str) -> str:
    text = _TAG_RE.sub("", html)
    text = (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    return _WS_RE.sub(" ", text).strip()


def truncate(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text

    truncated = text[:max_length]
    last_space = truncated.rfind(" ")

    if last_space > max_length * 0.8:
        return truncated[:last_space] + "..."

    return truncated + "..."


_IMG_SRC_RE = re.compile(r'<img\s[^>]*src=["\']([^"\']+)["\']', re.IGNORECASE)


def extract_image_from_html(html: str) -> str | None:
    match = _IMG_SRC_RE.search(html)
    return match.group(1) if match else None
