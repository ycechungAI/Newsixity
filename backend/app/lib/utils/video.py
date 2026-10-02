"""Video URL parsing and YouTube playlist fetching.

URL parsing is a port of src/lib/utils/video.ts. Playlist fetching is not:
the TS version ran in the browser against YouTube's RSS feed, which cannot
work there (youtube.com sends no CORS headers) and caps at 15 items anyway.
See ``fetch_youtube_playlist`` for what replaced it.
"""

from __future__ import annotations

import html as html_module
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Literal, Optional
from urllib.parse import parse_qs, urlparse

import httpx

from app.db.repository.videos import get_cached_playlist, save_cached_playlist
from app.lib.integrations.content import resolves_to_blocked_ip
from app.lib.utils.url import parse_http_url

logger = logging.getLogger(__name__)


VideoType = Literal["youtube", "vimeo", "dailymotion", "odysee", "animex", "unknown"]


@dataclass
class VideoInfo:
    type: VideoType
    video_id: str
    embed_url: str
    playlist_id: Optional[str] = None
    playlist_embed_url: Optional[str] = None


def extract_video_info(url: str) -> Optional[VideoInfo]:
    """Extract video information from a URL.

    Supports YouTube, Vimeo, Dailymotion, Odysee, and Animex.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname.lower() if parsed.hostname else ""

        # YouTube playlist ID (shared across YouTube URL types)
        query_params = parse_qs(parsed.query)
        yt_playlist_id = query_params.get("list", [None])[0]
        yt_playlist = {}
        if yt_playlist_id:
            yt_playlist = {
                "playlist_id": yt_playlist_id,
                "playlist_embed_url": f"https://www.youtube.com/embed/videoseries?list={yt_playlist_id}",
            }

        # YouTube hosts
        yt_hosts = [
            "youtube.com", "www.youtube.com", "m.youtube.com",
            "music.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com",
        ]
        is_youtube_host = hostname in yt_hosts

        # YouTube playlist-only URL (/playlist?list=PLxxx)
        if is_youtube_host and parsed.path == "/playlist":
            if yt_playlist_id:
                return VideoInfo(
                    type="youtube",
                    video_id="",
                    embed_url=f"https://www.youtube.com/embed/videoseries?list={yt_playlist_id}",
                    **yt_playlist,
                )

        # YouTube standard video
        if is_youtube_host:
            video_id = query_params.get("v", [None])[0]
            if video_id:
                return VideoInfo(
                    type="youtube",
                    video_id=video_id,
                    embed_url=f"https://www.youtube.com/embed/{video_id}",
                    **yt_playlist,
                )

        # YouTube short link (youtu.be)
        if hostname == "youtu.be":
            path_parts = [p for p in parsed.path.split("/") if p]
            if path_parts:
                video_id = path_parts[0]
                return VideoInfo(
                    type="youtube",
                    video_id=video_id,
                    embed_url=f"https://www.youtube.com/embed/{video_id}",
                    **yt_playlist,
                )

        # YouTube Shorts
        if is_youtube_host and parsed.path.startswith("/shorts/"):
            video_id = parsed.path.split("/shorts/")[1]
            if video_id:
                return VideoInfo(
                    type="youtube",
                    video_id=video_id,
                    embed_url=f"https://www.youtube.com/embed/{video_id}",
                )

        # Vimeo
        if hostname in ["vimeo.com", "www.vimeo.com"]:
            path_parts = [p for p in parsed.path.split("/") if p]
            if path_parts and path_parts[0].isdigit():
                video_id = path_parts[0]
                return VideoInfo(
                    type="vimeo",
                    video_id=video_id,
                    embed_url=f"https://player.vimeo.com/video/{video_id}",
                )

        # Dailymotion
        if hostname in ["www.dailymotion.com", "dailymotion.com"]:
            match = re.search(r"/video/([a-zA-Z0-9]+)", parsed.path)
            if match:
                video_id = match.group(1)
                return VideoInfo(
                    type="dailymotion",
                    video_id=video_id,
                    embed_url=f"https://www.dailymotion.com/embed/video/{video_id}?autoplay=0&mute=1",
                )

        # Dailymotion short link (dai.ly)
        if hostname == "dai.ly":
            video_id = parsed.path.lstrip("/")
            if video_id:
                return VideoInfo(
                    type="dailymotion",
                    video_id=video_id,
                    embed_url=f"https://www.dailymotion.com/embed/video/{video_id}?autoplay=0&mute=1",
                )

        # Odysee
        if hostname in ["odysee.com", "www.odysee.com"]:
            path = parsed.path
            if len(path) > 1 and not path.startswith("/$/"):
                return VideoInfo(
                    type="odysee",
                    video_id=path,
                    embed_url=f"https://odysee.com/$/embed{path}",
                )

        # Animex.one — anime streaming site
        if hostname in ["animex.one", "www.animex.one"]:
            if parsed.path.startswith("/watch/"):
                episode_id = parsed.path.split("/watch/")[1]
                if episode_id:
                    return VideoInfo(
                        type="animex",
                        video_id=episode_id,
                        embed_url=url,
                    )

        return None
    except Exception:
        return None


def is_video_url(url: str) -> bool:
    """Check if a URL is a video URL."""
    return extract_video_info(url) is not None


@dataclass
class PlaylistItem:
    title: str
    video_id: str
    url: str


# ── YouTube playlist fetching ────────────────────────────────────────────
#
# YouTube's RSS feed (the old approach) is unusable for two independent
# reasons: it returns no Access-Control-Allow-Origin header, so the browser
# blocks it outright, and it hard-caps at 15 items while silently ignoring
# the start-index/max-results parameters the old code passed (verified: all
# three variants return the identical 15 entries). Both are fixed by doing
# the fetch server-side against the playlist *page*, whose embedded
# ytInitialData blob carries 100 entries plus a continuation token for more.

# Playlist ids are opaque YouTube identifiers. Validate before interpolating
# one into a URL so a crafted "id" can't reshape the request.
PLAYLIST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{2,64}$")

PLAYLIST_TIMEOUT_SECONDS = 15
# YouTube serves a stripped page without ytInitialData to unrecognised agents.
PLAYLIST_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
# The first page load yields 100 items and each continuation round ~100 more.
# Bound both the total and the wall-clock spend so one enormous playlist
# can't stall the request.
PLAYLIST_MAX_ITEMS = 1000
PLAYLIST_TIME_BUDGET_SECONDS = 60
PLAYLIST_CACHE_TTL_SECONDS = 6 * 60 * 60

# playlist_id -> (expires_at_monotonic, payload). Hot cache for the current
# process; `youtube_playlist_cache` (app/db/repository/videos.py) is the durable
# layer that survives a restart. Scraping pulls ~2 MB per round and playlists
# change rarely, so both layers matter.
_playlist_cache: dict[str, tuple[float, dict]] = {}


def _guarded_get(url: str, **kwargs: Any) -> httpx.Response:
    """Fetch a URL through the same SSRF gate the rest of the app uses.

    These URLs are built from a validated id against a hardcoded host, so
    this is defence in depth rather than the primary control — but it keeps
    every outbound fetch in the codebase going through one door (see
    app.lib.podcast.parser.fetch_podcast_feed).
    """
    safe_url = parse_http_url(url)
    if not safe_url:
        raise ValueError("Not a valid http/https URL")
    if resolves_to_blocked_ip(urlparse(safe_url).hostname):
        raise ValueError("URL resolves to a blocked address")

    response = httpx.get(
        safe_url,
        timeout=PLAYLIST_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={"User-Agent": PLAYLIST_USER_AGENT},
        **kwargs,
    )
    response.raise_for_status()
    return response


def _lockup_entry(node: dict) -> Optional[tuple[str, str]]:
    """Read a ``lockupViewModel`` entry -> (video_id, title), if it is one."""
    lockup = node.get("lockupViewModel")
    if not isinstance(lockup, dict):
        return None
    video_id = lockup.get("contentId")
    if not video_id:
        return None
    title = lockup.get("metadata", {}).get("lockupMetadataViewModel", {}).get("title", {})
    title_text = title.get("content") if isinstance(title, dict) else None
    return video_id, title_text or "Untitled"


def _renderer_entry(node: dict) -> Optional[tuple[str, str]]:
    """Read a ``playlistVideoRenderer`` entry -> (video_id, title), if it is one.

    Title here is a runs-list ({"runs": [{"text": ...}]}) rather than the
    flat ``content`` string lockupViewModel uses.
    """
    renderer = node.get("playlistVideoRenderer")
    if not isinstance(renderer, dict):
        return None
    video_id = renderer.get("videoId")
    if not video_id:
        return None

    title = renderer.get("title")
    title_text = None
    if isinstance(title, dict):
        runs = title.get("runs")
        if isinstance(runs, list) and runs:
            title_text = "".join(r.get("text", "") for r in runs if isinstance(r, dict))
        elif isinstance(title.get("simpleText"), str):
            title_text = title["simpleText"]
    return video_id, title_text or "Untitled"


def _collect_lockups(
    root: Any, items: list[PlaylistItem], seen: set[str]
) -> list[str]:
    """Walk a ytInitialData/InnerTube tree, appending videos in document order.

    Returns **every** continuation token found, in document order, because
    more than one is present and they are not equivalent. A playlist page
    carries a token under ``continuationEndpoint`` that returns an empty
    response, alongside one under ``commands`` that returns the next 100
    videos. Keeping only the last-seen token picked the dead one and
    pagination stopped silently at 100 items.

    The caller tries each in turn and keeps the first that yields videos,
    rather than hardcoding a path that YouTube will reshuffle again.

    Reads BOTH entry shapes, and that is deliberate. YouTube has served this
    page as ``playlistVideoRenderer``, then ``lockupViewModel``, then
    ``playlistVideoRenderer`` again — the flip is not a one-way migration,
    it looks like an A/B test, and a scraper keyed to whichever one was live
    at the time silently collects nothing when it flips back. That failure
    is invisible: the walk succeeds and simply returns zero items.

    Callers must still treat an empty result as "the shape changed" and fall
    back, rather than as "the playlist is empty".

    Iterative rather than recursive: these trees nest deeply enough to risk
    the interpreter's recursion limit.
    """
    tokens: list[str] = []
    stack: list[Any] = [root]

    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            entry = _lockup_entry(node) or _renderer_entry(node)
            if entry:
                video_id, title_text = entry
                if video_id not in seen:
                    seen.add(video_id)
                    items.append(
                        PlaylistItem(
                            # Titles arrive HTML-escaped ("Batman &amp; Robin");
                            # unescape once here so every caller gets clean text.
                            title=html_module.unescape(title_text),
                            video_id=video_id,
                            url=f"https://www.youtube.com/watch?v={video_id}",
                        )
                    )

            command = node.get("continuationCommand")
            if isinstance(command, dict) and command.get("token"):
                tok = command["token"]
                if tok not in tokens:
                    tokens.append(tok)

            # Reversed so popping off the stack preserves document order.
            stack.extend(reversed(list(node.values())))
        elif isinstance(node, list):
            stack.extend(reversed(node))

    return tokens


def _extract_initial_data(html: str) -> Optional[dict]:
    match = re.search(r"var ytInitialData\s*=\s*(\{.*?\});</script>", html, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _fetch_continuation(api_key: str, client_version: str, token: str) -> Optional[dict]:
    """Ask InnerTube for the next ~100 playlist entries."""
    response = httpx.post(
        f"https://www.youtube.com/youtubei/v1/browse?key={api_key}",
        json={
            "context": {
                "client": {"clientName": "WEB", "clientVersion": client_version}
            },
            "continuation": token,
        },
        timeout=PLAYLIST_TIMEOUT_SECONDS,
        headers={"User-Agent": PLAYLIST_USER_AGENT},
    )
    response.raise_for_status()
    return response.json()


def _fetch_playlist_rss(playlist_id: str) -> list[PlaylistItem]:
    """Last-resort fallback: YouTube's RSS feed. Always exactly 15 items."""
    response = _guarded_get(
        f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"
    )
    xml = response.text

    items: list[PlaylistItem] = []
    for match in re.finditer(r"<entry>([\s\S]*?)</entry>", xml):
        block = match.group(1)
        title = re.search(r"<title>([^<]+)</title>", block)
        video_id = re.search(r"<yt:videoId>([^<]+)</yt:videoId>", block)
        if title and video_id:
            items.append(
                PlaylistItem(
                    title=title.group(1),
                    video_id=video_id.group(1),
                    url=f"https://www.youtube.com/watch?v={video_id.group(1)}",
                )
            )
    return items


def fetch_youtube_playlist(playlist_id: str, force_refresh: bool = False) -> dict:
    """Fetch a YouTube playlist's full contents.

    Returns ``{"items": [...], "totalItems": int, "source": str}`` where
    source is "scrape" (the page + continuations), "rss" (degraded, 15
    items) or "none". Callers paginate for display; everything is returned
    in one response.

    Never raises for a fetch/parse failure — an empty item list is returned
    so a transient YouTube problem degrades the playlist sidebar rather
    than failing the request.
    """
    if not PLAYLIST_ID_RE.match(playlist_id or ""):
        return {"items": [], "totalItems": 0, "source": "none"}

    # Two cache layers. The in-process dict is the hot path (no DB round trip
    # for repeated requests in one session); the `youtube_playlist_cache` table
    # is what makes a playlist survive a restart. It used to be the dict alone,
    # so every launch began cold — and a slow first fetch is exactly what leaves
    # the frontend's `/embed/videoseries?list=...` placeholder ("Video
    # unavailable") on screen, because that URL form has no video in it until a
    # real video id arrives.
    cached = _playlist_cache.get(playlist_id)
    if cached and cached[0] > time.monotonic() and not force_refresh:
        return cached[1]

    if not force_refresh:
        stored = get_cached_playlist(playlist_id)
        if stored is not None:
            payload = stored["payload"]
            _playlist_cache[playlist_id] = (
                time.monotonic() + PLAYLIST_CACHE_TTL_SECONDS,
                payload,
            )
            return payload

    items: list[PlaylistItem] = []
    seen: set[str] = set()
    source = "scrape"
    deadline = time.monotonic() + PLAYLIST_TIME_BUDGET_SECONDS

    try:
        html = _guarded_get(
            f"https://www.youtube.com/playlist?list={playlist_id}"
        ).text
        data = _extract_initial_data(html)
        tokens = _collect_lockups(data, items, seen) if data else []

        if not items:
            # Either the playlist really is empty or, far more likely,
            # YouTube changed the renderer key again. Degrade to RSS rather
            # than reporting an empty playlist.
            logger.warning(
                "Playlist %s: no lockupViewModel entries found; falling back to RSS",
                playlist_id,
            )
            items = _fetch_playlist_rss(playlist_id)
            source = "rss" if items else "none"
        elif tokens:
            api_key = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html)
            client_version = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', html)
            if api_key and client_version:
                tried: set[str] = set()

                while (
                    tokens
                    and len(items) < PLAYLIST_MAX_ITEMS
                    and time.monotonic() < deadline
                ):
                    # A page offers several tokens and only one of them
                    # actually returns videos; the others answer 200 with an
                    # empty body. Try each until one makes progress.
                    progressed = False
                    for token in tokens:
                        if token in tried:
                            continue
                        tried.add(token)
                        try:
                            page = _fetch_continuation(
                                api_key.group(1), client_version.group(1), token
                            )
                        except Exception as exc:  # noqa: BLE001
                            # Best-effort: keep whatever earlier rounds got.
                            logger.warning(
                                "Playlist %s: continuation failed after %d items: %s",
                                playlist_id,
                                len(items),
                                exc,
                            )
                            continue

                        before = len(items)
                        next_tokens = _collect_lockups(page, items, seen)
                        if len(items) > before:
                            tokens = next_tokens
                            progressed = True
                            break

                    if not progressed:
                        break  # Nothing left that yields videos.

                del items[PLAYLIST_MAX_ITEMS:]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Playlist %s: fetch failed: %s", playlist_id, exc)
        return {"items": [], "totalItems": 0, "source": "none"}

    result = {
        "items": [
            {"title": i.title, "videoId": i.video_id, "url": i.url} for i in items
        ],
        "totalItems": len(items),
        "source": source,
    }
    _playlist_cache[playlist_id] = (
        time.monotonic() + PLAYLIST_CACHE_TTL_SECONDS,
        result,
    )
    # Persist so the next launch is warm. A write failure must not fail the
    # fetch — the result is already good and the in-memory copy still serves.
    try:
        save_cached_playlist(playlist_id, result, PLAYLIST_CACHE_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Playlist %s: could not persist cache: %s", playlist_id, exc)
    return result
