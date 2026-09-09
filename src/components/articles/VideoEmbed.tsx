"use client";

import { useCallback, useEffect, useState } from "react";
import {
  extractVideoInfo,
  fetchYouTubePlaylist,
  isLinux,
  youtubePlayableUrl,
  type PlaylistItem,
} from "@/lib/utils/video";
import { useVideoPlayer, useVideoSlot } from "@/lib/video/playerContext";

/** Videos listed per page. The whole playlist is already loaded — this is
 *  purely how much of it is shown at once. */
const PLAYLIST_PAGE_SIZE = 15;

/** Remembers the autoplay-next choice across navigation and restarts. */
const AUTOPLAY_KEY = "newsixity.video.autoplayNext";

const SIZE_PRESETS = [
  { label: "S", pct: 50 },
  { label: "M", pct: 75 },
  { label: "L", pct: 100 },
];

interface VideoEmbedProps {
  url: string;
  title?: string;
  className?: string;
  playlistItems?: PlaylistItem[];
  /**
   * Route playback through the app-wide player (resizable, pop-out, PiP).
   * Only the article detail page sets this: the card grid renders many
   * videos at once and there is exactly one shared player, so cards keep
   * their own lightweight inline iframes.
   */
  shared?: boolean;
  /** Identity for the shared player — the article id. */
  slotKey?: string;
  /** Re-scrape the playlist, bypassing the backend's 6-hour cache. */
  onRefreshPlaylist?: () => Promise<void>;
}

export default function VideoEmbed({
  url,
  title,
  playlistItems,
  shared = false,
  slotKey,
  onRefreshPlaylist,
}: VideoEmbedProps) {
  const videoInfo = extractVideoInfo(url);
  const [currentEmbedUrl, setCurrentEmbedUrl] = useState(
    // Linux: WebKit has no Widevine, so YouTube iframes never play. Route the
    // video through our backend's DRM-free stream into a native <video>. On
    // Windows/macOS the iframe embed is the original, working path — leave it.
    isLinux && videoInfo?.type === "youtube" && !!videoInfo?.videoId
      ? youtubePlayableUrl(videoInfo.videoId, videoInfo?.playlistId)
      : (videoInfo?.embedUrl ?? "")
  );
  const [currentTitle, setCurrentTitle] = useState(title ?? "");
  const [activeVideoId, setActiveVideoId] = useState(videoInfo?.videoId ?? "");
  const [playlistPage, setPlaylistPage] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [fetchedPlaylistItems, setFetchedPlaylistItems] = useState<PlaylistItem[]>();
  const effectivePlaylistItems = playlistItems ?? fetchedPlaylistItems;

  // Cards in Others and Saved use this component directly, rather than the
  // article page. Fetch the playlist here as a fallback so a playlist-only
  // URL starts with its first real video instead of YouTube's unusable
  // /embed/videoseries placeholder in those views.
  useEffect(() => {
    if (playlistItems !== undefined || !videoInfo?.playlistId) return;
    let cancelled = false;
    fetchYouTubePlaylist(videoInfo.playlistId).then((result) => {
      if (!cancelled) setFetchedPlaylistItems(result.items);
    });
    return () => { cancelled = true; };
  }, [playlistItems, videoInfo?.playlistId]);

  // Keyed off the CURRENT video (activeVideoId), not the original URL: a
  // playlist-only link starts with no videoId, and only resolves to a real
  // video once the playlist loads — after which native streaming must apply.
  const hasActiveLinuxYouTube =
    isLinux && videoInfo?.type === "youtube" && !!activeVideoId;

  const { dockWidthPct, setDockWidthPct } = useVideoPlayer();

  /** Continue to the next playlist entry when one finishes. Persisted, so
   *  the choice survives navigation and restarts. */
  const [autoplayNext, setAutoplayNext] = useState(() => {
    try {
      return localStorage.getItem(AUTOPLAY_KEY) === "1";
    } catch {
      return false;
    }
  });

  const toggleAutoplay = useCallback(() => {
    setAutoplayNext((on) => {
      const next = !on;
      try {
        localStorage.setItem(AUTOPLAY_KEY, next ? "1" : "0");
      } catch {
        // Private mode / storage disabled — the toggle still works for
        // this session.
      }
      return next;
    });
  }, []);

  /**
   * A playlist-only link (youtube.com/playlist?list=...) has no video id, so
   * extractVideoInfo falls back to an /embed/videoseries?list=... URL. That
   * form renders "Video unavailable" — there is no video in it to play —
   * which looked like a broken video even though clicking any playlist entry
   * worked fine, because that swaps in a real /embed/<id> URL.
   *
   * Once the playlist resolves, start on its first video instead. The list
   * parameter is kept so YouTube still treats it as a playlist.
   */
  useEffect(() => {
    if (activeVideoId) return;                       // A real video is loaded.
    if (!videoInfo?.playlistId) return;              // Not a playlist link.
    const first = effectivePlaylistItems?.[0];
    if (!first) return;                              // Not fetched yet.

    setCurrentEmbedUrl(
      youtubePlayableUrl(first.videoId, videoInfo.playlistId)
    );
    setCurrentTitle(first.title);
    setActiveVideoId(first.videoId);
  }, [activeVideoId, effectivePlaylistItems, videoInfo?.playlistId]);

  /**
   * Advance to the next playlist entry when the current one finishes.
   *
   * The host owns playback and reports the end (YouTube's postMessage
   * playerState 0, or the native `ended` event for direct files); only this
   * component knows what "next" means, so the decision lives here.
   *
   * autoplay=1 is required on the next URL — without it the embed loads the
   * video but waits for a click, which would stall the chain after one
   * video. Pausing does not fire "ended", so a user pause stops the chain
   * naturally, as does switching the toggle off.
   */
  useEffect(() => {
    if (!autoplayNext || !effectivePlaylistItems?.length) return;

    const onEnded = () => {
      const index = effectivePlaylistItems.findIndex((i) => i.videoId === activeVideoId);
      const next = index >= 0 ? effectivePlaylistItems[index + 1] : undefined;
      if (!next) return;  // End of the playlist — stop rather than loop.

      const nextUrl = hasActiveLinuxYouTube
        ? youtubePlayableUrl(next.videoId, videoInfo?.playlistId)
        : `https://www.youtube.com/embed/${next.videoId}?autoplay=1` +
          (videoInfo?.playlistId ? `&list=${videoInfo.playlistId}` : "");
      setCurrentEmbedUrl(nextUrl);
      setCurrentTitle(next.title);
      setActiveVideoId(next.videoId);

      // Keep the visible page in step, so the highlighted entry stays on screen.
      setPlaylistPage(Math.floor((index + 1) / PLAYLIST_PAGE_SIZE));
    };

    window.addEventListener("video-ended", onEnded);
    return () => window.removeEventListener("video-ended", onEnded);
  }, [autoplayNext, effectivePlaylistItems, activeVideoId, videoInfo?.playlistId, hasActiveLinuxYouTube]);

  const isAnimex = videoInfo?.type === "animex";
  const isDirect = videoInfo?.type === "direct";
  // Linux WebKitGTK has no Widevine and its GStreamer media path can abort the
  // WebKitWebProcess when asked to play YouTube's extracted stream. Keep the
  // playlist UI in-app, but hand the selected YouTube video to the user's
  // browser instead of creating either an iframe or a native media element.
  const isLinuxYouTube = isLinux && videoInfo?.type === "youtube";
  const isNative =
    isDirect || (!isLinux && videoInfo?.type === "youtube" && !!activeVideoId);

  /**
   * Canonical YouTube page for whatever is loaded right now.
   *
   * Tracks the playlist selection rather than the article's original URL, so
   * "open on YouTube" opens the video actually on screen. Falls back to the
   * playlist itself when no individual video has been picked yet.
   */
  const watchUrl =
    videoInfo?.type !== "youtube"
      ? null
      : activeVideoId
        ? `https://www.youtube.com/watch?v=${activeVideoId}` +
          (videoInfo.playlistId ? `&list=${videoInfo.playlistId}` : "")
        : videoInfo.playlistId
          ? `https://www.youtube.com/playlist?list=${videoInfo.playlistId}`
          : null;
  // Animex is a plain link-out, so it never takes over the shared player.
  const useShared = shared && !!videoInfo && !isAnimex && !isLinuxYouTube;

  const slotRef = useVideoSlot(
    useShared
      ? {
          key: slotKey ?? url,
          embedUrl: currentEmbedUrl,
          title: currentTitle,
          kind: isNative ? "video" : "iframe",
        }
      : null
  );

  const startResize = useCallback(
    (event: React.PointerEvent) => {
      event.preventDefault();
      const container = slotRef.current?.parentElement;
      if (!container) return;
      const containerWidth = container.getBoundingClientRect().width;
      const startX = event.clientX;
      const startPct = dockWidthPct;

      const onMove = (e: PointerEvent) => {
        const deltaPct = ((e.clientX - startX) / containerWidth) * 100;
        setDockWidthPct(startPct + deltaPct);
      };
      const onUp = () => {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [dockWidthPct, setDockWidthPct, slotRef]
  );

  if (!videoInfo) return null;

  return (
    <div>
      {useShared ? (
        <>
          {/* Placeholder only — the actual player is mounted once at the app
              root and positions itself over this box, so it is never
              re-parented (which would reload the iframe). */}
          <div
            ref={slotRef}
            className="card-video is-slot"
            style={{ width: `${dockWidthPct}%` }}
          />
          <div className="video-size-bar">
            <span className="video-size-label">Size</span>
            {SIZE_PRESETS.map((preset) => (
              <button
                key={preset.label}
                className={`video-size-btn${
                  Math.round(dockWidthPct) === preset.pct ? " active" : ""
                }`}
                onClick={() => setDockWidthPct(preset.pct)}
              >
                {preset.label}
              </button>
            ))}
            <span
              className="video-size-grip"
              onPointerDown={startResize}
              title="Drag to resize"
            />
            {/* Embeds run with most YouTube controls suppressed, and some
                videos refuse to embed at all (owner-disabled, age-gated, or
                region-locked) — which shows as a player that never starts.
                This is the escape hatch: same video, full controls, and it
                works even when the embed cannot. */}
            {watchUrl && (
              <a
                className="video-size-link"
                href={watchUrl}
                target="_blank"
                rel="noopener noreferrer"
                title="Open on YouTube with full controls"
              >
                ↗ YouTube
              </a>
            )}
          </div>
        </>
      ) : (
        /* 16:9 embed container */
        <div className="card-video">
          {isLinuxYouTube ? (
            <a
              href={watchUrl ?? url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ display: "flex", alignItems: "center", justifyContent: "center", background: "#171717", color: "#fff", fontSize: 12, textDecoration: "none" }}
            >
              ▶ Open on YouTube
            </a>
          ) : isAnimex ? (
            <a href={url} target="_blank" rel="noopener noreferrer"
              style={{ display: "flex", alignItems: "center", justifyContent: "center", background: "#1a0a2e", color: "#fff", fontSize: 12, textDecoration: "none" }}
            >
              ▶ Watch on Animex.one
            </a>
          ) : isNative ? (
            <video
              src={currentEmbedUrl}
              title={currentTitle}
              controls
              style={{ width: "100%", height: "100%", objectFit: "contain" }}
            />
          ) : (
            <iframe
              src={currentEmbedUrl}
              title={currentTitle}
              allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              loading="lazy"
            />
          )}
        </div>
      )}

      {/* Playlist (article detail page only) */}
      {effectivePlaylistItems && effectivePlaylistItems.length > 0 && (() => {
        const pageCount = Math.ceil(effectivePlaylistItems.length / PLAYLIST_PAGE_SIZE);
        const start = playlistPage * PLAYLIST_PAGE_SIZE;
        const pageItems = effectivePlaylistItems.slice(start, start + PLAYLIST_PAGE_SIZE);

        return (
          <div className="vid-playlist">
            <div className="vid-playlist-title">
              <span>Playlist ({effectivePlaylistItems.length} videos)</span>
              {/* The backend caches a playlist for 6 hours keyed by playlist
                  id, so videos added or removed on YouTube stay invisible —
                  and deleting the article does not help, because that only
                  changes a database row. This forces a re-scrape. */}
              {onRefreshPlaylist && (
                <button
                  className="vid-autoplay-btn"
                  disabled={refreshing}
                  title="Re-fetch from YouTube (ignores the cached copy)"
                  onClick={async () => {
                    setRefreshing(true);
                    try {
                      await onRefreshPlaylist();
                      setPlaylistPage(0);
                    } finally {
                      setRefreshing(false);
                    }
                  }}
                >
                  {refreshing ? "Syncing…" : "↻ Sync"}
                </button>
              )}
              <button
                className={`vid-autoplay-btn${autoplayNext ? " active" : ""}`}
                onClick={toggleAutoplay}
                aria-pressed={autoplayNext}
                title={
                  autoplayNext
                    ? "Autoplay is on — the next video starts automatically. Pausing stops it."
                    : "Autoplay is off — videos stop at the end."
                }
              >
                {autoplayNext ? "⏭ Autoplay on" : "⏭ Autoplay off"}
              </button>
            </div>
            <ol>
              {pageItems.map((item, i) => (
                <li key={item.videoId}>
                  {/* Number against the whole playlist, not the page. */}
                  <span className="vid-playlist-num">{start + i + 1}.</span>
                  <button
                    className={`vid-playlist-btn${activeVideoId === item.videoId ? " active" : ""}`}
                    onClick={() => {
                      setCurrentEmbedUrl(
                        youtubePlayableUrl(item.videoId, videoInfo?.playlistId)
                      );
                      setCurrentTitle(item.title);
                      setActiveVideoId(item.videoId);
                    }}
                  >
                    {item.title}
                  </button>
                </li>
              ))}
            </ol>

            {/* Every item is already in memory, so paging is instant and
                costs no network request. */}
            {pageCount > 1 && (
              <div className="vid-playlist-pages">
                {Array.from({ length: pageCount }, (_, p) => (
                  <button
                    key={p}
                    className={`vid-playlist-page${p === playlistPage ? " active" : ""}`}
                    onClick={() => setPlaylistPage(p)}
                    aria-current={p === playlistPage ? "page" : undefined}
                  >
                    {p * PLAYLIST_PAGE_SIZE + 1}–
                    {Math.min((p + 1) * PLAYLIST_PAGE_SIZE, effectivePlaylistItems.length)}
                  </button>
                ))}
              </div>
            )}
          </div>
        );
      })()}
    </div>
  );
}
