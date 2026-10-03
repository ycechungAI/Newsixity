import { useCallback, useEffect, useState } from "react";
import { resolveShareLink, type ResolvedShareLink } from "@/lib/utils/video";

interface ShareLinkViewProps {
  url: string;
  title?: string;
}

/**
 * A publisher share link — most often a PCloud *folder*.
 *
 * These are not media files, so they deliberately do not go through
 * VideoEmbed: a `<video>` pointed at a folder shows a dead player and reports
 * nothing. The backend is asked what the link actually is first, because the
 * answer decides between three genuinely different UIs:
 *
 *  - **media** — it does resolve to a file. Play it natively.
 *  - **page, framable** — a listing. Show it in the mini browser below, which
 *    is what the user asked for: the folder, then click a video, it plays.
 *  - **anything else** — say so, and hand them the link. Never show a blank
 *    frame: a cross-origin frame refused by `X-Frame-Options` renders as an
 *    empty rectangle with no error in any console, which is the failure mode
 *    this component exists to avoid.
 */
export default function ShareLinkView({ url, title }: ShareLinkViewProps) {
  const [result, setResult] = useState<ResolvedShareLink | null>(null);
  /** Bumped to re-probe; a share link's target can change behind it. */
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setResult(null);
    void resolveShareLink(url, controller.signal).then(setResult);
    return () => controller.abort();
  }, [url, attempt]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);

  const openExternally = (
    <a
      className="share-open-btn"
      href={url}
      target="_blank"
      rel="noopener noreferrer"
    >
      Open in browser ↗
    </a>
  );

  if (!result) {
    return (
      <div className="share-view is-loading" role="status">
        Checking this link…
      </div>
    );
  }

  // A file behind the share link: play it like any other direct video.
  if (result.kind === "media" && result.url) {
    return (
      <video
        className="share-view-media"
        src={result.url}
        title={title}
        controls
      />
    );
  }

  // A listing we are allowed to frame: the mini browser.
  if (result.kind === "page" && result.url && result.framable) {
    return (
      <div className="share-view">
        <div className="share-view-bar">
          <span className="share-view-url" title={result.url}>{result.url}</span>
          <button className="act-btn" onClick={reload} title="Reload">↺</button>
          {openExternally}
        </div>
        <iframe
          className="share-view-frame"
          src={result.url}
          title={title ?? "Shared files"}
          loading="lazy"
          // Same permissions the rest of the app gives framed pages: enough to
          // run the publisher's own player, no top-navigation escape hatches.
          sandbox="allow-same-origin allow-scripts allow-popups allow-forms allow-pointer-lock"
        />
        <div className="share-view-hint">
          Pick a file in the list above and it plays here.
        </div>
      </div>
    );
  }

  // Not framable, or not playable at all. Say which, and hand over the link —
  // a folder share is still perfectly usable in the user's own browser, where
  // they are signed in and the publisher's frame policy does not apply.
  return (
    <div className="share-view is-blocked">
      <div className="share-view-msg">
        {result.reason ?? "This link can't be played here."}
      </div>
      <div className="share-view-actions">
        {openExternally}
        <button className="act-btn" onClick={reload} title="Try again">↺ Try again</button>
      </div>
    </div>
  );
}