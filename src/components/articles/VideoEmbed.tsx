"use client";

import { useCallback, useState } from "react";
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

  const isAnimex = videoInfo?.type === "animex";
  const isDirect = videoInfo?.type === "direct";
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
