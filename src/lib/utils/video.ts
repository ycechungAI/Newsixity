export interface VideoInfo {
  type: 'youtube' | 'vimeo' | 'dailymotion' | 'odysee' | 'unknown';
  videoId: string;
  embedUrl: string;
}

/**
 * Extract video information from a URL
 * Supports YouTube and Vimeo
 */
export function extractVideoInfo(url: string): VideoInfo | null {
  try {
    const urlObj = new URL(url);

    // YouTube
    if (urlObj.hostname === 'youtube.com' || urlObj.hostname === 'www.youtube.com') {
      const videoId = urlObj.searchParams.get('v');
      if (videoId) {
        return {
          type: 'youtube',
          videoId,
          embedUrl: `https://www.youtube.com/embed/${videoId}`,
        };
      }
    }

    // YouTube short link
    if (urlObj.hostname === 'youtu.be') {
      const videoId = urlObj.pathname.slice(1);
      if (videoId) {
        return {
          type: 'youtube',
          videoId,
          embedUrl: `https://www.youtube.com/embed/${videoId}`,
        };
      }
    }

    // YouTube Shorts
    if (urlObj.hostname === 'www.youtube.com' && urlObj.pathname.startsWith('/shorts/')) {
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
          embedUrl: `https://www.dailymotion.com/embed/video/${videoId}`,
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
          embedUrl: `https://www.dailymotion.com/embed/video/${videoId}`,
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
