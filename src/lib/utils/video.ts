export interface VideoInfo {
  type: 'youtube' | 'vimeo' | 'dailymotion' | 'odysee' | 'animex' | 'direct' | 'unknown';
  videoId: string;
  embedUrl: string;
  playlistId?: string;
  playlistEmbedUrl?: string;
  /**
   * True when the URL is a *page* that redirects to the media file, so the
   * browser must not use `embedUrl` directly. PCloud share links have no file
   * extension — the shape below matches them and nothing else, because a
   * generic "resolve any URL" would turn every article link into a fetch.
   */
  viaServer?: boolean;
}

/** Hosts whose share links resolve to a playable file via /api/videos/direct.
 *
 * Matched on the registrable domain, so `e.pcloud.link` and `my.pcloud.com`
 * qualify while `pcloud.link.evil.example` does not. */
const SHARE_LINK_HOSTS = ['pcloud.com', 'pcloud.link', 'pc.cd'];

/** A publisher share link: a page URL with no media file extension. */
export function isShareLink(url: string): boolean {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return SHARE_LINK_HOSTS.some((d) => host === d || host.endsWith('.' + d));
  } catch {
    return false;
  }
}

/**
 * The URL to hand a `<video src>`.
 *
 * Share links go through the backend, which follows the redirects and answers
 * 307 — the final file is usually on another host with no CORS headers, so the
 * browser cannot follow the hop itself. Everything else is used as-is.
 */
export function playableSrc(url: string): string {
  if (!isShareLink(url)) return url;
  return `/api/videos/direct?url=${encodeURIComponent(url)}`;
}

/**
 * Linux webviews (WebKitGTK) have no Widevine, so YouTube iframe embeds never
 * play there — Windows (WebView2) and macOS (WKWebView) ship DRM and the
 * embed just works. The Linux fix routes YouTube through our backend's
 * DRM-free /api/videos/stream endpoint into a native <video> element.
 *
 * Detected from the user agent; other platforms are left on the embed path
 * untouched so their (working) playback never changes.
 */
export const isLinux =
  typeof navigator !== "undefined" && /Linux/i.test(navigator.userAgent);

/** True on the packaged macOS app (WKWebView). */
export const isMacOS =
  typeof navigator !== "undefined" &&
  /Macintosh|Mac OS X/i.test(navigator.userAgent) &&
  !/iPhone|iPad|iPod/i.test(navigator.userAgent);

/** True on the packaged Windows app (WebView2). */
export const isWindows =
  typeof navigator !== "undefined" && /Windows/i.test(navigator.userAgent);

/** Stream URL for a YouTube video on Linux, else the direct iframe embed URL. */
export function youtubePlayableUrl(videoId: string, playlistId?: string, maxHeight = 720): string {
  const base = `https://www.youtube.com/embed/${encodeURIComponent(videoId)}`;
  if (!isLinux) {
    return playlistId ? `${base}?list=${encodeURIComponent(playlistId)}` : base;
  }
  const watch =
    `https://www.youtube.com/watch?v=${encodeURIComponent(videoId)}` +
    (playlistId ? `&list=${encodeURIComponent(playlistId)}` : "");
  return `/api/videos/stream?url=${encodeURIComponent(watch)}&maxHeight=${maxHeight}`;
}

/** True when the current platform embeds YouTube via an iframe (default). */
export function shouldIframeYouTube(): boolean {
  return !isLinux;
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
        // A share link that happens to end in .mp4 still 302s to the real
        // file, so it takes the same server path as the extensionless form.
        viaServer: isShareLink(url),
      };
    }

    // Publisher share links: a page URL that redirects to the media file.
    // Checked *after* the extension test so a real .mp4 keeps its identity,
    // and before the null return because these carry no extension at all —
    // which is why they produced no player before.
    if (isShareLink(url)) {
      return {
        type: 'direct',
        videoId: url,
        embedUrl: url,
        viaServer: true,
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

export interface PlaylistResult {
  items: PlaylistItem[];
  totalItems: number;
  /** "scrape" = full playlist, "rss" = degraded to 15, "none" = unavailable. */
  source: "scrape" | "rss" | "none";
}

/**
 * Fetch a YouTube playlist's full contents via our backend.
 *
 * This deliberately does NOT call youtube.com directly. That's what the
 * previous version did, and it could never work: youtube.com sends no
 * Access-Control-Allow-Origin header, so the browser blocked every request
 * and the catch below quietly returned an empty list — the playlist sidebar
 * has been silently empty ever since the move off Next.js. The RSS feed it
 * used also caps at 15 items and ignores pagination parameters entirely.
 *
 * The backend returns every video in one response (see
 * backend/app/lib/utils/video.py); callers paginate for display.
 */
/**
 * playlist_id -> in-flight-or-resolved promise.
 *
 * VideoEmbed falls back to fetching its own playlist when the list view doesn't
 * supply `playlistItems` (Others and Saved both do this), so a grid of cards
 * for the same playlist would otherwise re-request per card. Storing the
 * promise rather than the result also de-dupes concurrent callers.
 *
 * Backing this is the backend's persistent `youtube_playlist_cache` table, so
 * a cold frontend memo still hits SQLite rather than YouTube.
 */
const playlistMemo = new Map<string, Promise<PlaylistResult>>();

export async function fetchYouTubePlaylist(
  playlistId: string,
  /** Re-scrape instead of using the backend's 6-hour cache. Needed after
   *  the playlist is edited on YouTube, since the cache is keyed by playlist
   *  id — deleting and re-adding the article does not invalidate it. */
  refresh = false
): Promise<PlaylistResult> {
  if (!refresh) {
    const memo = playlistMemo.get(playlistId);
    // An in-flight promise is shared rather than duplicated, so a grid of
    // cards for the same playlist issues one request, not one per card.
    if (memo) return memo;
  }

  const pending = fetchPlaylistUncached(playlistId, refresh);
  // A refresh replaces the memo too, so the user sees the re-scraped list.
  playlistMemo.set(playlistId, pending);

  try {
    const result = await pending;
    // Don't memoise an empty scrape — the next mount should be free to retry.
    if (result.items.length === 0) playlistMemo.delete(playlistId);
    return result;
  } catch (err) {
    playlistMemo.delete(playlistId);
    throw err;
  }
}

async function fetchPlaylistUncached(
  playlistId: string,
  refresh: boolean
): Promise<PlaylistResult> {
  const empty: PlaylistResult = { items: [], totalItems: 0, source: "none" };
  try {
    const res = await fetch(
      `/api/videos/playlist?id=${encodeURIComponent(playlistId)}${refresh ? "&refresh=true" : ""}`,
      // A forced re-scrape re-walks every continuation page, so allow longer.
      { signal: AbortSignal.timeout(refresh ? 90000 : 30000) }
    );
    if (!res.ok) return empty;
    return (await res.json()) as PlaylistResult;
  } catch {
    return empty;
  }
}
