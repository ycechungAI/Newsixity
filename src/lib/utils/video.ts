export interface VideoInfo {
  type: 'youtube' | 'vimeo' | 'dailymotion' | 'odysee' | 'animex' | 'direct' | 'unknown';
  videoId: string;
  embedUrl: string;
  playlistId?: string;
  playlistEmbedUrl?: string;
}

/**
 * Extract video information from a URL
 * Supports YouTube and Vimeo
 */
export function extractVideoInfo(url: string): VideoInfo | null {
  try {
    const urlObj = new URL(url);
    const hostname = urlObj.hostname.toLowerCase();
    const isYouTubeHost = [
      "youtube.com",
      "www.youtube.com",
      "m.youtube.com",
      "music.youtube.com",
      "youtube-nocookie.com",
      "www.youtube-nocookie.com",
    ].includes(hostname);

    // YouTube playlist ID (shared across YouTube URL types)
    const ytPlaylistId = urlObj.searchParams.get('list') || undefined;
    const ytPlaylist = ytPlaylistId
      ? { playlistId: ytPlaylistId, playlistEmbedUrl: `https://www.youtube.com/embed/videoseries?list=${ytPlaylistId}` }
      : {};

    // YouTube playlist-only URL (/playlist?list=PLxxx)
    if (isYouTubeHost && urlObj.pathname === '/playlist') {
      if (ytPlaylistId) {
        return {
          type: 'youtube',
          videoId: '',
          embedUrl: `https://www.youtube.com/embed/videoseries?list=${ytPlaylistId}`,
          ...ytPlaylist,
        };
      }
    }

    // YouTube standard video
    if (isYouTubeHost) {
      const videoId = urlObj.searchParams.get('v');
      if (videoId) {
        return {
          type: 'youtube',
          videoId,
          embedUrl: `https://www.youtube.com/embed/${videoId}`,
          ...ytPlaylist,
        };
      }
    }

    // YouTube short link
    if (hostname === 'youtu.be') {
      const videoId = urlObj.pathname.split("/").filter(Boolean)[0];
      if (videoId) {
        return {
          type: 'youtube',
          videoId,
          embedUrl: `https://www.youtube.com/embed/${videoId}`,
          ...ytPlaylist,
        };
      }
    }

    // YouTube Shorts
    if (isYouTubeHost && urlObj.pathname.startsWith('/shorts/')) {
      const videoId = urlObj.pathname.split('/shorts/')[1];
      if (videoId) {
        return {
          type: 'youtube',
          videoId,
          embedUrl: `https://www.youtube.com/embed/${videoId}`,
        };
      }
    }

    // Vimeo
    if (urlObj.hostname === 'vimeo.com' || urlObj.hostname === 'www.vimeo.com') {
      const videoId = urlObj.pathname.split('/').filter(Boolean)[0];
      if (videoId && /^\d+$/.test(videoId)) {
        return {
          type: 'vimeo',
          videoId,
          embedUrl: `https://player.vimeo.com/video/${videoId}`,
        };
      }
    }

    // Dailymotion
    if (urlObj.hostname === 'www.dailymotion.com' || urlObj.hostname === 'dailymotion.com') {
      const videoId = urlObj.pathname.match(/\/video\/([a-zA-Z0-9]+)/)?.[1];
      if (videoId) {
        return {
          type: 'dailymotion',
          videoId,
          embedUrl: `https://www.dailymotion.com/embed/video/${videoId}?autoplay=0&mute=1`,
        };
      }
    }

    // Dailymotion short link
    if (urlObj.hostname === 'dai.ly') {
      const videoId = urlObj.pathname.slice(1);
      if (videoId) {
        return {
          type: 'dailymotion',
          videoId,
          embedUrl: `https://www.dailymotion.com/embed/video/${videoId}?autoplay=0&mute=1`,
        };
      }
    }

    // Odysee
    if (urlObj.hostname === 'odysee.com' || urlObj.hostname === 'www.odysee.com') {
      const path = urlObj.pathname;
      // Odysee video paths contain @ for channels or direct video slugs
      if (path.length > 1 && !path.startsWith('/$/')) {
        return {
          type: 'odysee',
          videoId: path,
          embedUrl: `https://odysee.com/$/embed${path}`,
        };
      }
    }

    // Animex.one - anime streaming site
    if (urlObj.hostname === 'animex.one' || urlObj.hostname === 'www.animex.one') {
      const path = urlObj.pathname;
      // Animex paths like /watch/episode-id
      if (path.startsWith('/watch/')) {
        const episodeId = path.split('/watch/')[1];
        if (episodeId) {
          return {
            type: 'animex',
            videoId: episodeId,
            embedUrl: url, // Use original URL as embed (site handles its own player)
          };
        }
      }
    }

    // Direct video files (mp4, mkv, webm, etc.)
    const directVideoExts = ['.mp4', '.mkv', '.webm', '.avi', '.mov', '.m3u8'];
    const pathname = urlObj.pathname.toLowerCase();
    if (directVideoExts.some(ext => pathname.endsWith(ext))) {
      return {
        type: 'direct',
        videoId: url,
        embedUrl: url,
      };
    }

    return null;
  } catch {
    return null;
  }
}

/**
 * Check if a URL is a video URL
 */
export function isVideoUrl(url: string): boolean {
  return extractVideoInfo(url) !== null;
}

export interface PlaylistItem {
  title: string;
  videoId: string;
  url: string;
}

export interface PlaylistPagination {
  currentPage: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
}

/**
 * Fetch YouTube playlist contents via RSS feed.
 * Returns up to 20 most recent videos (10 per page, max 2 pages).
 */
export async function fetchYouTubePlaylist(
  playlistId: string,
  options?: { page?: number; pageSize?: number }
): Promise<{ items: PlaylistItem[]; pagination: PlaylistPagination }> {
  const page = options?.page ?? 1;
  const pageSize = options?.pageSize ?? 10;

  try {
    // YouTube RSS feeds support start-index and max-results parameters
    // start-index is 1-based, max-results maxes out at 15-20 for playlists
    const startIndex = (page - 1) * pageSize + 1;
    const feedUrl = `https://www.youtube.com/feeds/videos.xml?playlist_id=${playlistId}&start-index=${startIndex}&max-results=${pageSize}`;
    const res = await fetch(feedUrl, { signal: AbortSignal.timeout(8000) });
    if (!res.ok) return { items: [], pagination: { currentPage: page, pageSize, totalItems: 0, totalPages: 0 } };

    const xml = await res.text();

    const items: PlaylistItem[] = [];
    const entryRegex = /<entry>([\s\S]*?)<\/entry>/g;
    let match;

    while ((match = entryRegex.exec(xml))) {
      const block = match[1];
      const title = block.match(/<title>([^<]+)<\/title>/)?.[1];
      const videoId = block.match(/<yt:videoId>([^<]+)<\/yt:videoId>/)?.[1];

      if (title && videoId) {
        items.push({ title, videoId, url: `https://www.youtube.com/watch?v=${videoId}` });
      }
    }

    // YouTube RSS only supports 1-2 pages max (capped at ~15-20 items total)
    const totalPages = page === 1 && items.length >= pageSize ? 2 : 1;

    return {
      items,
      pagination: {
        currentPage: page,
        pageSize,
        totalItems: items.length,
        totalPages,
      },
    };
  } catch {
    return { items: [], pagination: { currentPage: page, pageSize, totalItems: 0, totalPages: 0 } };
  }
}
