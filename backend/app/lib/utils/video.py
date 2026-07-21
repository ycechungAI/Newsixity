"""Video URL parsing and playlist fetching — port of src/lib/utils/video.ts."""

import re
from dataclasses import dataclass
from typing import Literal, Optional
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen
from urllib.error import URLError
import socket


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


@dataclass
class PlaylistPagination:
    current_page: int
    page_size: int
    total_items: int
    total_pages: int


def fetch_youtube_playlist(
    playlist_id: str,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    """Fetch YouTube playlist contents via RSS feed.

    Returns up to 20 most recent videos (10 per page, max 2 pages).
    Accepts pagination options.
    """
    try:
        start_index = (page - 1) * page_size + 1
        feed_url = (
            f"https://www.youtube.com/feeds/videos.xml?"
            f"playlist_id={playlist_id}&"
            f"start-index={start_index}&"
            f"max-results={page_size}"
        )

        socket.setdefaulttimeout(8)
        res = urlopen(feed_url)
        if res.status != 200:
            return {
                "items": [],
                "pagination": PlaylistPagination(page, page_size, 0, 0).__dict__,
            }
        xml = res.read().decode("utf-8")

        items: list[PlaylistItem] = []
        entry_regex = r"<entry>([\s\S]*?)<\/entry>"

        for match in re.finditer(entry_regex, xml):
            block = match.group(1)
            title_match = re.search(r"<title>([^<]+)<\/title>", block)
            video_id_match = re.search(r"<yt:videoId>([^<]+)<\/yt:videoId>", block)

            if title_match and video_id_match:
                title = title_match.group(1)
                video_id = video_id_match.group(1)
                items.append(PlaylistItem(
                    title=title,
                    video_id=video_id,
                    url=f"https://www.youtube.com/watch?v={video_id}",
                ))

        # YouTube RSS only supports 1-2 pages max (capped at ~15-20 items total)
        total_pages = 2 if (page == 1 and len(items) >= page_size) else 1

        return {
            "items": [item.__dict__ for item in items],
            "pagination": PlaylistPagination(
                page, page_size, len(items), total_pages
            ).__dict__,
        }
    except (URLError, socket.timeout, Exception):
        return {
            "items": [],
            "pagination": PlaylistPagination(page, page_size, 0, 0).__dict__,
        }
