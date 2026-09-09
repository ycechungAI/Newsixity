"""Direct-stream resolution for embedded videos (YouTube especially).

Why this exists: WebKitGTK — the webview engine the Linux AppImage uses —
has no Widevine/DRM support, so YouTube iframe embeds never play on Linux
(every Windows/macOS build uses a browser engine that ships DRM and the
embed just works). The Linux fix is to bypass the embed entirely and feed the
``<video>`` element a plain, DRM-free MP4 stream.

Two things make that non-trivial these days:

* YouTube rarely offers a combined audio+video "progressive" stream any more
  (it split video and audio into separate DASH formats years ago). When no
  combined format exists we remux the best video-only + audio-only pair with
  ffmpeg into a fragmented MP4 piped straight back to the client — no
  re-encode, so latency is a few seconds and CPU stays near zero.
* YouTube requires a browser-y request. We extract the stream URLs with
  yt-dlp (that's what it is for), then feed them to ffmpeg rather than
  hitting googlevideo blindly.

The endpoint is one or the other per request:
  * a combined format exists  -> 307 redirect straight to the direct URL, or
  * only split formats exist  -> 200 video/mp4 fMP4 pipe (remuxed by ffmpeg).

yt-dlp is imported lazily like the other optional integrations (ollama): the
backend still boots if it or ffmpeg is missing, and only /api/videos/stream
reports that it cannot serve. The resolver has no runtime dependency on
``fetch_youtube_playlist``; it shares only the video-id parsing.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from app.lib.utils.video import extract_video_info

logger = logging.getLogger(__name__)

# Resolved playable choices are cached per video id. The googlevideo URLs yt-dlp
# returns are signed and expire in hours; a short TTL keeps them usable while
# avoiding a 2-5 s yt-dlp extraction on every play or playlist advance.
STREAM_CACHE_TTL_SECONDS = 30 * 60

# Max height requested unless the caller overrides. Keeps CPU/bandwidth sane
# for a news-reading app; embed-quality (<=720p) is plenty for an article.
DEFAULT_MAX_HEIGHT = 720

# YouTube responds with a captcha or empty payload to unrecognised agents.
STREAM_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class StreamChoice:
    """One playable way to watch a video: a direct URL, or a v/a pair to mux."""

    direct_url: str | None = None
    v_url: str | None = None
    a_url: str | None = None
    title: str = ""

    @property
    def has_direct(self) -> bool:
        return bool(self.direct_url)

    @property
    def needs_mux(self) -> bool:
        return bool(self.v_url and self.a_url)

    @property
    def usable(self) -> bool:
        return bool(self.direct_url or (self.v_url and self.a_url))

    def as_dict(self) -> dict[str, Any]:
        return {
            "directUrl": self.direct_url,
            "vUrl": self.v_url,
            "aUrl": self.a_url,
            "title": self.title,
        }


_cache: dict[str, tuple[float, StreamChoice]] = {}
_cache_lock = threading.Lock()


class StreamError(Exception):
    """Raised with a user-presentable message when a stream cannot be served."""


# Lazy import so the rest of the backend loads even when yt-dlp is absent
# (PyInstaller still collects it via the spec's collect_all for yt_dlp).
_yt_dlp: Any | None = None


def _load_yt_dlp() -> Any:
    global _yt_dlp
    if _yt_dlp is None:
        try:
            import yt_dlp

            _yt_dlp = yt_dlp
        except ImportError:
            raise StreamError(
                "yt-dlp is not bundled with this build; cannot stream "
                "YouTube videos on Linux."
            ) from None
    return _yt_dlp


def _find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise StreamError(
            "ffmpeg is not installed; cannot combine YouTube's separate "
            "video/audio streams. Install ffmpeg to watch videos on Linux."
        )
    return exe


def _pick_format(
    formats: list[dict[str, Any]], want: str, max_height: int
) -> dict[str, Any] | None:
    """Pick the best format of a kind.

    ``want`` is "combined" (has audio AND video), "video" (video-only) or
    "audio" (audio-only). Criteria applied in order: direct HTTP URLs first
    (no m3u8), progressive MP4 (H.264/AAC) preferred, height capped at
    max_height, else the next-best single format.
    """
    if not formats:
        return None

    def full(f: dict[str, Any]) -> bool:
        both = f.get("acodec") not in (None, "none") and f.get("vcodec") not in (None, "none")
        if want == "combined":
            return both
        if want == "video":
            return f.get("vcodec") not in (None, "none")
        return f.get("acodec") not in (None, "none")

    def direct(f: dict[str, Any]) -> bool:
        proto = f.get("protocol") or ""
        return bool(proto) and not proto.startswith("m3u8")

    def mp4ish(f: dict[str, Any]) -> bool:
        return (f.get("vcodec") or "").startswith("avc1") or (f.get("ext") or "") == "mp4"

    def aacish(f: dict[str, Any]) -> bool:
        return (f.get("acodec") or "").startswith("mp4a") or (f.get("ext") or "") in ("m4a", "mp4")

    def h_ok(f: dict[str, Any]) -> bool:
        h = f.get("height")
        return h in (None, 0) or h <= max_height

    candidates = [f for f in formats if full(f) and direct(f) and h_ok(f)]
    if not candidates:
        candidates = [f for f in formats if full(f) and direct(f)]  # any height
    if not candidates:
        return None

    if want == "combined":
        return max(candidates, key=lambda f: (mp4ish(f), aacish(f), f.get("height") or 0))
    if want == "video":
        return max(candidates, key=lambda f: (mp4ish(f), f.get("height") or 0))
    return max(candidates, key=lambda f: (aacish(f), f.get("abr") or f.get("tbr") or 0))


def resolve_stream(
    url: str,
    max_height: int = DEFAULT_MAX_HEIGHT,
    _force: bool = False,
) -> StreamChoice:
    """Resolve a playable stream for a video URL.

    Cached per video id for STREAM_CACHE_TTL_SECONDS. Raises StreamError with a
    user-facing message when nothing playable is found. ``max_height`` only
    matters for fresh resolutions; a cached direct URL is served as-is.
    """
    info = extract_video_info(url)
    if not info or info.type != "youtube" or not info.video_id:
        raise StreamError("Only YouTube video URLs can be streamed this way.")

    video_id = info.video_id

    with _cache_lock:
        cached = _cache.get(video_id)
    if cached and not _force and cached[0] > time.monotonic() and (
        # A muxed pair caps at the requested height; if the caller asked for
        # a higher cap than what's cached, re-resolve rather than serve lower.
        max_height == DEFAULT_MAX_HEIGHT or cached[1].has_direct
    ):
        return cached[1]

    choice = _resolve_uncached(url, video_id, max_height)

    with _cache_lock:
        _cache[video_id] = (time.monotonic() + STREAM_CACHE_TTL_SECONDS, choice)
    return choice


def _resolve_uncached(url: str, video_id: str, max_height: int) -> StreamChoice:
    ydl = _load_yt_dlp()

    try:
        with ydl.YoutubeDL(
            {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "noplaylist": True,
                "socket_timeout": 15,
            }
        ) as dl:
            info = dl.extract_info(url, download=False)
    except Exception as exc:  # noqa: BLE001 — member-only, removed, geo-blocked…
        logger.warning("Stream resolve failed for %s: %s", video_id, exc)
        raise StreamError(
            f"This video cannot be streamed: {type(exc).__name__}"
        ) from None

    formats: list[dict[str, Any]] = info.get("formats") or []
    choice = StreamChoice(title=info.get("title") or "")

    combined = _pick_format(formats, "combined", max_height)
    if combined:
        choice.direct_url = combined.get("url")
    else:
        v = _pick_format(formats, "video", max_height)
        a = _pick_format(formats, "audio", max_height)
        if v and a:
            choice.v_url = v.get("url")
            choice.a_url = a.get("url")

    if not choice.usable:
        raise StreamError("No playable format could be resolved for this video.")

    return choice


def iter_ffmpeg_mux(choice: StreamChoice) -> Iterator[bytes]:
    """Yield remuxed fMP4 chunks from video-only + audio-only URLs.

    ffmpeg copies the codecs (no re-encode) into a fragmented MP4 on stdout so
    the client can start playback in a couple of seconds.
    """
    if not choice.needs_mux or not choice.v_url or not choice.a_url:
        raise StreamError("A video/audio pair is required to mux a stream.")

    cmd = [
        _find_ffmpeg(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-user_agent",
        STREAM_USER_AGENT,
        "-i",
        choice.v_url,
        "-i",
        choice.a_url,
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "copy",
        "-movflags",
        "frag_keyframe+empty_moov+default_base_moof",
        "-sn",
        "-dn",
        "-f",
        "mp4",
        "pipe:1",
    ]

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    assert proc.stdout is not None
    try:
        while True:
            chunk = proc.stdout.read(65536)
            if not chunk:
                break
            yield chunk
    finally:
        proc.kill()
        proc.wait()


def stream_cache_info() -> dict[str, Any]:
    """Internal/console helper: how many resolutions are cached and when they expire."""
    now = time.monotonic()
    entries = [
        {"videoId": vid, "expiresInSeconds": max(0, int(pair[0] - now))}
        for vid, pair in list(_cache.items())
    ]
    return {"count": len(entries), "entries": entries[:50]}