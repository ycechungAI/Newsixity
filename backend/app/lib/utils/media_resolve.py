"""Resolving media share links to something a <video> element can play.

Some publishers hand out a *page* URL rather than a file: PCloud's share links
(`my.pcloud.com/publink/show?code=…`, `e.pcloud.link/publink/getlink/…`) carry
no file extension, so the frontend's extension check can't tell they are video
and never mounts a player. Following the link server-side lands on the real
media URL, which is then handed back as a redirect the browser follows directly
— the same shape as the YouTube DRM-free stream path, and for the same reason:
the final CDN URL is usually on another host with no CORS headers, so it cannot
be fetched from the browser at all.

The redirect walk re-checks the SSRF gate on every hop. That is the whole point
of doing this here rather than in the browser: with ``follow_redirects=True`` a
public URL can 302 to 127.0.0.1 and a single up-front check never sees it. The
same rule, and the same helpers, as ``rss.fetch_feed_bytes``.

Only headers are read — the media body is never buffered. Resolving a 2 GB file
must not pull 2 GB through the server.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

from app.lib.integrations.content import resolves_to_blocked_ip
from app.lib.utils.url import parse_http_url

logger = logging.getLogger("newsixity")

# Resolution is a handshake, not a download: a share link answers in well under
# a second. Keep the timeout short so a dead host fails fast in the UI instead
# of leaving a spinner on the card.
RESOLVE_TIMEOUT_SECONDS = 10.0

# Bounded like the feed fetcher. Two is typical for PCloud (share page → CDN);
# the cap exists so a redirect loop cannot spin forever.
MAX_RESOLVE_REDIRECTS = 5

# Content types a browser can hand straight to <video src>.
_VIDEO_CONTENT_PREFIXES = ("video/", "application/vnd.apple.mpegurl", "application/x-mpegurl")

# Hosts whose share links we know resolve to a media file. Kept as a list
# rather than a suffix test so an unrelated lookalike domain cannot opt itself
# into the redirect path.
_PUBLISHERS = (
    "pcloud.com",
    "pcloud.link",
    "pc.cd",
)


class ShareLinkError(ValueError):
    """The link could not be resolved to playable media. User-facing."""


@dataclass(frozen=True)
class ResolvedMedia:
    """A share link that turned out to be a real, playable media file."""

    url: str
    content_type: str


def is_known_share_host(url: str) -> bool:
    """Whether this URL is a share link we can resolve.

    Matches the registrable domain, so `e.pcloud.link`, `my.pcloud.com` and
    `u.pcloud.link` all qualify while `pcloud.link.evil.example` does not.
    """
    safe = parse_http_url(url)
    if not safe:
        return False
    host = (urlparse(safe).hostname or "").lower()
    if not host:
        return False
    return any(host == d or host.endswith("." + d) for d in _PUBLISHERS)


def _check_url(url: str) -> str:
    """The SSRF gate, applied to one hop. Raises rather than returning None.

    Both conditions fail closed, and neither is distinguishable from the other
    at the call site, so the message names both possibilities rather than
    claiming the address was private.
    """
    safe = parse_http_url(url)
    if not safe:
        raise ShareLinkError("That link can't be opened: it isn't an http(s) URL")
    host = urlparse(safe).hostname or ""
    if not host or resolves_to_blocked_ip(host):
        raise ShareLinkError("That link can't be resolved from this computer")
    return safe


def resolve_share_link(url: str) -> ResolvedMedia:
    """Follow a share link to the media file behind it.

    Raises ShareLinkError with a user-facing reason when the link does not
    resolve to video — which is a normal outcome, not an error: plenty of
    share links are folders, images, or multi-file shares that no <video>
    element can play.
    """
    current = _check_url(url)

    with httpx.Client(
        timeout=RESOLVE_TIMEOUT_SECONDS,
        follow_redirects=False,
    ) as client:
        for _hop in range(MAX_RESOLVE_REDIRECTS + 1):
            # stream() so the body is never read: we want the headers, and a
            # media file can be arbitrarily large.
            with client.stream(
                "GET",
                current,
                headers={
                    # PCloud serves a login/interstitial page to obvious bots,
                    # which is indistinguishable from "not a video".
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0 Safari/537.36"
                    ),
                    "Accept": "*/*",
                },
            ) as response:
                if response.is_redirect:
                    location = response.headers.get("location", "")
                    if not location:
                        raise ShareLinkError("That link redirects nowhere useful")
                    current = _check_url(urljoin(current, location))
                    continue

                if response.status_code >= 400:
                    raise ShareLinkError(
                        f"That link returned HTTP {response.status_code}"
                    )

                content_type = (
                    response.headers.get("content-type", "") or ""
                ).split(";")[0].strip().lower()

                if content_type.startswith(_VIDEO_CONTENT_PREFIXES):
                    return ResolvedMedia(url=current, content_type=content_type)

                if not content_type or content_type.startswith(
                    ("text/html", "application/xhtml")
                ):
                    raise ShareLinkError(
                        "That link is a web page, not a playable video file"
                    )

                raise ShareLinkError(
                    f"That link is not a video (it serves {content_type})"
                )

    raise ShareLinkError("That link redirects too many times")