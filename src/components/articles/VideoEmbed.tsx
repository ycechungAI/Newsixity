"use client";

import { useCallback, useEffect, useState } from "react";
import { extractVideoInfo, type PlaylistItem } from "@/lib/utils/video";
import { useVideoPlayer, useVideoSlot } from "@/lib/video/playerContext";

/** Videos listed per page. The whole playlist is already loaded — this is
 *  purely how much of it is shown at once. */
const PLAYLIST_PAGE_SIZE = 15;

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
}

export default function VideoEmbed({
  url,
  title,
  playlistItems,
  shared = false,
  slotKey,
}: VideoEmbedProps) {
  const videoInfo = extractVideoInfo(url);
  const [currentEmbedUrl, setCurrentEmbedUrl] = useState(videoInfo?.embedUrl ?? "");
  const [currentTitle, setCurrentTitle] = useState(title ?? "");
  const [activeVideoId, setActiveVideoId] = useState(videoInfo?.videoId ?? "");
  const [playlistPage, setPlaylistPage] = useState(0);

  const { dockWidthPct, setDockWidthPct } = useVideoPlayer();

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
    const first = playlistItems?.[0];
    if (!first) return;                              // Not fetched yet.

    setCurrentEmbedUrl(
      `https://www.youtube.com/embed/${first.videoId}?list=${videoInfo.playlistId}`
    );
    setCurrentTitle(first.title);
    setActiveVideoId(first.videoId);
  }, [activeVideoId, playlistItems, videoInfo?.playlistId]);

  const isAnimex = videoInfo?.type === "animex";
  const isDirect = videoInfo?.type === "direct";

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
  const useShared = shared && !!videoInfo && !isAnimex;

  const slotRef = useVideoSlot(
    useShared
      ? {
          key: slotKey ?? url,
          embedUrl: currentEmbedUrl,
          title: currentTitle,
          kind: isDirect ? "video" : "iframe",
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
          {isAnimex ? (
            <a href={url} target="_blank" rel="noopener noreferrer"
              style={{ display: "flex", alignItems: "center", justifyContent: "center", background: "#1a0a2e", color: "#fff", fontSize: 12, textDecoration: "none" }}
            >
              ▶ Watch on Animex.one
            </a>
          ) : isDirect ? (
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
      {playlistItems && playlistItems.length > 0 && (() => {
        const pageCount = Math.ceil(playlistItems.length / PLAYLIST_PAGE_SIZE);
        const start = playlistPage * PLAYLIST_PAGE_SIZE;
        const pageItems = playlistItems.slice(start, start + PLAYLIST_PAGE_SIZE);

        return (
          <div className="vid-playlist">
            <div className="vid-playlist-title">
              Playlist ({playlistItems.length} videos)
            </div>
            <ol>
              {pageItems.map((item, i) => (
                <li key={item.videoId}>
                  {/* Number against the whole playlist, not the page. */}
                  <span className="vid-playlist-num">{start + i + 1}.</span>
                  <button
                    className={`vid-playlist-btn${activeVideoId === item.videoId ? " active" : ""}`}
                    onClick={() => {
                      setCurrentEmbedUrl(`https://www.youtube.com/embed/${item.videoId}`);
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
                    {Math.min((p + 1) * PLAYLIST_PAGE_SIZE, playlistItems.length)}
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
