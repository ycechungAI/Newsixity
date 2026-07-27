"""Video helpers that must run server-side.

Playlist contents are fetched here rather than in the browser because
youtube.com sends no CORS headers — the old client-side fetch was blocked
by every browser and silently returned an empty list.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.lib.server.rate_limit import TEN_MIN_MS, rate_limit
from app.lib.utils.video import PLAYLIST_ID_RE, fetch_youtube_playlist

router = APIRouter()


@router.get(
    "/videos/playlist",
    dependencies=[Depends(rate_limit("videos-playlist", 60, TEN_MIN_MS))],
)
def get_youtube_playlist(id: str = Query(..., description="YouTube playlist id")) -> dict:
    """Return a playlist's full contents; the client paginates for display."""
    if not PLAYLIST_ID_RE.match(id):
        raise HTTPException(status_code=400, detail="Invalid playlist id")
    return fetch_youtube_playlist(id)
