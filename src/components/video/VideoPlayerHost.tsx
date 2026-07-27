"use client";

/**
 * A single, always-mounted video player shared by the whole app.
 *
 * The reason this exists rather than each page rendering its own <iframe>:
 * moving an iframe in the DOM reloads it, losing playback position. So the
 * player is mounted once above the router and *never re-parented*. Pages
 * render an empty placeholder ("slot"); the host measures that slot and
 * positions itself over it. Popping out, or navigating to another page,
 * only changes CSS — the iframe element itself never moves, so playback
 * continues uninterrupted.
 *
 * The one exception is Document Picture-in-Picture, which by definition
 * moves the node into another window; see requestPip below.
 */

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { VideoPlayerContext, type ActiveVideo } from "@/lib/video/playerContext";

interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}

const DOCK_WIDTH_KEY = "newsixity.video.dockWidthPct";
const FLOAT_WIDTH_KEY = "newsixity.video.floatWidth";
const MIN_DOCK_PCT = 40;
const MAX_DOCK_PCT = 100;
const MIN_FLOAT_WIDTH = 240;
const MAX_FLOAT_WIDTH = 900;

function readStored(key: string, fallback: number, min: number, max: number): number {
  const raw = Number(localStorage.getItem(key));
  return Number.isFinite(raw) && raw >= min && raw <= max ? raw : fallback;
}

/** YouTube answers a "listening" handshake only when enablejsapi=1 is set. */
function withJsApi(url: string): string {
  if (!url.includes("youtube.com/embed/")) return url;
  if (url.includes("enablejsapi=")) return url;
  return url + (url.includes("?") ? "&" : "?") + "enablejsapi=1";
}

function withStart(url: string, seconds: number): string {
  if (seconds < 1) return url;
  const stripped = url.replace(/([?&])start=\d+/, "$1");
  return stripped + (stripped.includes("?") ? "&" : "?") + `start=${Math.floor(seconds)}`;
}

export function VideoPlayerProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState<ActiveVideo | null>(null);
  const [slot, setSlot] = useState<HTMLElement | null>(null);
  const [floating, setFloating] = useState(false);
  const [rect, setRect] = useState<Rect | null>(null);
  const [dockWidthPct, setDockWidthPctState] = useState(100);
  const [floatWidth, setFloatWidth] = useState(400);

  const containerRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<HTMLDivElement>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  /** Last known playback position, used to resume across a Document-PiP move. */
  const currentTimeRef = useRef(0);

  useEffect(() => {
    setDockWidthPctState(readStored(DOCK_WIDTH_KEY, 100, MIN_DOCK_PCT, MAX_DOCK_PCT));
    setFloatWidth(readStored(FLOAT_WIDTH_KEY, 400, MIN_FLOAT_WIDTH, MAX_FLOAT_WIDTH));
  }, []);

  const setDockWidthPct = useCallback((pct: number) => {
    const clamped = Math.min(MAX_DOCK_PCT, Math.max(MIN_DOCK_PCT, pct));
    setDockWidthPctState(clamped);
    localStorage.setItem(DOCK_WIDTH_KEY, String(Math.round(clamped)));
  }, []);

  const claim = useCallback((video: ActiveVideo, el: HTMLElement | null) => {
    setActive((prev) =>
      prev && prev.key === video.key && prev.embedUrl === video.embedUrl ? prev : video
    );
    setSlot(el);
    setFloating(false);
  }, []);

  // The slot going away (navigating off the article page) is not a reason to
  // stop playing — that's exactly when the floating player earns its keep.
  const release = useCallback((key: string) => {
    setSlot(null);
    setActive((prev) => (prev && prev.key === key ? prev : prev));
    setFloating(true);
  }, []);

  const close = useCallback(() => {
    setActive(null);
    setSlot(null);
    setFloating(false);
  }, []);

  // Track the slot's position so the fixed-position player can sit on top of
  // it. Capture-phase scroll catches scrolling inside nested containers too.
  //
  // dockWidthPct is an explicit dependency rather than being left to the
  // ResizeObserver: this effect runs after React has applied the new width,
  // so the measurement is correct and synchronous. ResizeObserver doesn't
  // fire while the page is throttled (background tab), which would
  // otherwise leave the player stranded at its old size.
  useLayoutEffect(() => {
    if (!slot || floating) return;
    const update = () => {
      const r = slot.getBoundingClientRect();
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(slot);
    window.addEventListener("scroll", update, true);
    window.addEventListener("resize", update);
    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
    };
  }, [slot, floating, dockWidthPct]);

  // Keep a running playback position for YouTube embeds. This uses the
  // IFrame API's postMessage protocol directly rather than loading YouTube's
  // SDK — one less external script, and it works under a strict CSP.
  useEffect(() => {
    if (!active || active.kind !== "iframe") return;
    currentTimeRef.current = 0;

    const handshake = () => {
      iframeRef.current?.contentWindow?.postMessage(
        JSON.stringify({ event: "listening", id: "newsixity" }),
        "*"
      );
    };
    const onMessage = (event: MessageEvent) => {
      if (!event.origin.includes("youtube.com")) return;
      try {
        const data = JSON.parse(event.data);
        const t = data?.info?.currentTime;
        if (typeof t === "number") currentTimeRef.current = t;
      } catch {
        // Non-JSON chatter from the embed; ignore.
      }
    };
    window.addEventListener("message", onMessage);
    const timer = setInterval(handshake, 1000);
    return () => {
      window.removeEventListener("message", onMessage);
      clearInterval(timer);
    };
  }, [active]);

  const pipMode: "native" | "document" | null = useMemo(() => {
    if (!active) return null;
    if (active.kind === "video") {
      return typeof document !== "undefined" && "pictureInPictureEnabled" in document
        ? "native"
        : null;
    }
    // A cross-origin iframe can't be handed to the native PiP API — only
    // Document PiP can float it, and that is Chromium-only. In WebKit
    // (which is what the packaged macOS app runs on) this is null and the
    // in-app floating player is the fallback.
    return typeof window !== "undefined" && "documentPictureInPicture" in window
      ? "document"
      : null;
  }, [active]);

  const requestPip = useCallback(async () => {
    if (pipMode === "native") {
      try {
        await videoRef.current?.requestPictureInPicture();
      } catch {
        // User gesture lost or PiP disabled; nothing useful to do.
      }
      return;
    }
    if (pipMode !== "document" || !playerRef.current) return;

    const player = playerRef.current;
    const rectNow = player.getBoundingClientRect();
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const pipWindow = await (window as any).documentPictureInPicture.requestWindow({
        width: Math.round(rectNow.width) || 480,
        height: Math.round(rectNow.height) || 270,
      });

      // Moving the node into another document reloads the iframe, so resume
      // where the user left off rather than restarting the video.
      const resumeAt = currentTimeRef.current;

      for (const sheet of Array.from(document.styleSheets)) {
        try {
          const css = Array.from(sheet.cssRules).map((r) => r.cssText).join("");
          const style = pipWindow.document.createElement("style");
          style.textContent = css;
          pipWindow.document.head.appendChild(style);
        } catch {
          // Cross-origin stylesheet; skip it.
        }
      }
      pipWindow.document.body.style.margin = "0";
      pipWindow.document.body.append(player);
      if (iframeRef.current && resumeAt > 1) {
        iframeRef.current.src = withStart(iframeRef.current.src, resumeAt);
      }

      pipWindow.addEventListener("pagehide", () => {
        containerRef.current?.append(player);
      });
    } catch {
      // Blocked or unsupported — the floating player still covers this.
    }
  }, [pipMode]);

  const startFloatResize = useCallback(
    (event: React.PointerEvent) => {
      event.preventDefault();
      const startX = event.clientX;
      const startWidth = floatWidth;
      const onMove = (e: PointerEvent) => {
        // Anchored bottom-right, so dragging left grows it.
        const next = Math.min(
          MAX_FLOAT_WIDTH,
          Math.max(MIN_FLOAT_WIDTH, startWidth + (startX - e.clientX))
        );
        setFloatWidth(next);
      };
      const onUp = () => {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        setFloatWidth((w) => {
          localStorage.setItem(FLOAT_WIDTH_KEY, String(Math.round(w)));
          return w;
        });
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [floatWidth]
  );

  const contextValue = useMemo(
    () => ({ active, claim, release, dockWidthPct, setDockWidthPct }),
    [active, claim, release, dockWidthPct, setDockWidthPct]
  );

  const isDocked = !floating && !!rect;
  const style: React.CSSProperties = isDocked
    ? {
        position: "fixed",
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
      }
    : {
        position: "fixed",
        right: 16,
        bottom: 16,
        width: floatWidth,
        height: Math.round((floatWidth * 9) / 16) + 28,
      };

  return (
    <VideoPlayerContext.Provider value={contextValue}>
      {children}
      {active && (
        <div
          ref={containerRef}
          className={`video-host${floating ? " is-floating" : ""}`}
          style={style}
        >
          <div ref={playerRef} className="video-host-player">
            {floating && (
              <div className="video-host-bar">
                <span className="video-host-title" title={active.title}>
                  {active.title}
                </span>
                {pipMode && (
                  <button className="video-host-btn" onClick={requestPip} title="Picture-in-picture">
                    ⧉
                  </button>
                )}
                {slot && (
                  <button className="video-host-btn" onClick={() => setFloating(false)} title="Dock">
                    ▣
                  </button>
                )}
                <button className="video-host-btn" onClick={close} title="Close">
                  ✕
                </button>
              </div>
            )}
            {active.kind === "video" ? (
              <video
                ref={videoRef}
                src={active.embedUrl}
                title={active.title}
                controls
                className="video-host-media"
              />
            ) : (
              <iframe
                ref={iframeRef}
                src={withJsApi(active.embedUrl)}
                title={active.title}
                allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
                className="video-host-media"
              />
            )}
          </div>

          {floating && (
            <div
              className="video-host-resize"
              onPointerDown={startFloatResize}
              title="Drag to resize"
            />
          )}
          {isDocked && (
            <div className="video-host-controls">
              {pipMode && (
                <button className="video-host-btn" onClick={requestPip} title="Picture-in-picture">
                  ⧉
                </button>
              )}
              <button
                className="video-host-btn"
                onClick={() => setFloating(true)}
                title="Pop out (keeps playing while you browse)"
              >
                ⇱
              </button>
            </div>
          )}
        </div>
      )}
    </VideoPlayerContext.Provider>
  );
}

