/**
 * Context and hooks for the app-wide video player.
 *
 * Kept separate from the provider component so that file only exports
 * components (React Fast Refresh requirement).
 * See src/components/video/VideoPlayerHost.tsx for why a single shared
 * player exists at all.
 */

import { createContext, useContext, useEffect, useRef } from "react";

export interface ActiveVideo {
  /** Stable identity for the source (article id). Changing embedUrl for the
   *  same key swaps the video without tearing down the slot. */
  key: string;
  embedUrl: string;
  title: string;
  kind: "iframe" | "video";
}

export interface VideoPlayerContextValue {
  active: ActiveVideo | null;
  claim: (video: ActiveVideo, el: HTMLElement | null) => void;
  release: (key: string) => void;
  /** Docked width as a percentage of the slot's container. */
  dockWidthPct: number;
  setDockWidthPct: (pct: number) => void;
}

export const VideoPlayerContext = createContext<VideoPlayerContextValue | null>(null);

export function useVideoPlayer(): VideoPlayerContextValue {
  const ctx = useContext(VideoPlayerContext);
  if (!ctx) throw new Error("useVideoPlayer must be used inside VideoPlayerProvider");
  return ctx;
}

/**
 * Reserve space for the shared player on a page. Returns a ref to attach to
 * the placeholder element; the host positions itself over it.
 */
export function useVideoSlot(video: ActiveVideo | null) {
  const { claim, release } = useVideoPlayer();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!video) return;
    claim(video, ref.current);
    return () => release(video.key);
    // Deps are primitives, so an inline object literal for `video` is safe.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [video?.key, video?.embedUrl, video?.kind, claim, release]);

  return ref;
}
