"""Video helpers that must run server-side.

Playlist contents are fetched here rather than in the browser because
youtube.com sends no CORS headers — the old client-side fetch was blocked
by every browser and silently returned an empty list.

Direct streaming also lives here: WebKitGTK (the Linux webview engine) has no
Widevine, so YouTube iframe embeds don't play on Linux. The frontend requests
a DRM-free stream from /videos/stream instead.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, StreamingResponse

from app.lib.server.rate_limit import TEN_MIN_MS, rate_limit
from app.lib.utils.stream import (
    DEFAULT_MAX_HEIGHT,
    StreamError,
    iter_ffmpeg_mux,
    resolve_stream,
    stream_cache_info,
)
from app.lib.utils.video import PLAYLIST_ID_RE, fetch_youtube_playlist

router = APIRouter()


@router.get(
    "/videos/playlist",
    dependencies=[Depends(rate_limit("videos-playlist", 60, TEN_MIN_MS))],
)
def get_youtube_playlist(
    id: str = Query(..., description="YouTube playlist id"),
    refresh: bool = Query(False, description="Bypass the cache and re-scrape"),
) -> dict:
    """Return a playlist's full contents; the client paginates for display.

    Results are cached in-process for 6 hours, so a playlist edited on
    YouTube keeps showing its old contents until that expires — and deleting
    the article does not help, because the cache is keyed by playlist id, not
    by article. ``refresh=true`` is the explicit way to re-scrape.
    """
    if not PLAYLIST_ID_RE.match(id):
        raise HTTPException(status_code=400, detail="Invalid playlist id")
    return fetch_youtube_playlist(id, force_refresh=refresh)


@router.get(
    "/videos/stream",
    dependencies=[Depends(rate_limit("videos-stream", 60, TEN_MIN_MS))],
)
def get_youtube_stream(
    url: str = Query(..., description="YouTube watch URL"),
    maxHeight: int = Query(
        DEFAULT_MAX_HEIGHT, ge=144, le=1080, description="Maximum video height"
    ),
):
    """Serve a DRM-free stream so videos play on Linux (no Widevine in WebKit).

    Prefer a single combined progressive URL — respond with a 307 so the
    ``<video>`` element follows it directly (seekable, zero backend load).
    Otherwise remux YouTube's separate video-only + audio-only DASH streams
    with ffmpeg into a fragmented MP4 piped straight back (copy codecs, no
    transcode) as ``video/mp4``.
    """
    try:
        choice = resolve_stream(url, max_height=maxHeight)
    except StreamError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if choice.has_direct and choice.direct_url:
        return RedirectResponse(choice.direct_url, status_code=307)

    headers = {
        "Cache-Control": "no-store",
        "X-Accel-Buffering": "no",
        "Content-Disposition": 'inline; filename="stream.mp4"',
    }
    return StreamingResponse(
        iter_ffmpeg_mux(choice),
        media_type="video/mp4",
        headers=headers,
    )


@router.get("/videos/stream-info", include_in_schema=False)
def dev_stream_cache() -> dict:
    """Console/debug helper: inspect the stream resolution cache."""
    return stream_cache_info()
