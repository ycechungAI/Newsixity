/**
 * Make off-site links open in the user's real browser.
 *
 * In a normal browser `target="_blank"` just works. In the packaged app's
 * WKWebView there is no new-window handler, so those clicks did nothing at
 * all — the same silent no-op class as window.confirm and blob downloads.
 *
 * The Rust side (src-tauri/src/lib.rs) intercepts any navigation away from
 * the app's own origin and hands it to the system browser. But a
 * `target="_blank"` click never becomes a navigation, so it never reaches
 * that handler. This bridges the gap.
 *
 * Detection is behavioural rather than sniffing for Tauri: `window.open`
 * returns a Window in a browser and null when the webview refuses. Only on
 * null do we fall back to signalling the Rust side. So the browser keeps its
 * new tab, the packaged app opens the system browser, and neither needs to
 * know which one it is.
 *
 * The signal is deliberately explicit. The Rust handler used to infer it —
 * treating any off-origin URL as a link click — but that callback also fires
 * for iframe loads, so every YouTube embed was cancelled and thrown at the
 * system browser: videos never played and the YouTube app opened over and
 * over. Now nothing leaves the app unless this file asks it to, by name.
 */

/** Must match OPEN_EXTERNAL_PATH in src-tauri/src/lib.rs. */
const OPEN_EXTERNAL_PATH = "/__newsixity/open-external";

/**
 * Ask the desktop shell to open `url` in the system browser.
 *
 * Sent as a navigation inside a throwaway hidden iframe rather than as a
 * top-level one: the shell cancels it, but if anything ever failed to, only
 * the invisible iframe would go astray — the app UI could not be replaced by
 * a page with no back button. Outside the packaged app the request 404s
 * unseen, and this path is only reached when window.open already failed.
 */
function requestExternalOpen(url: string): void {
  const frame = document.createElement("iframe");
  frame.hidden = true;
  frame.style.display = "none";
  frame.src = `${OPEN_EXTERNAL_PATH}?url=${encodeURIComponent(url)}`;
  document.body.appendChild(frame);
  window.setTimeout(() => frame.remove(), 1000);
}

function isExternal(url: URL): boolean {
  if (url.origin === window.location.origin) return false;
  return url.protocol === "http:" || url.protocol === "https:";
}

export function installExternalLinkHandler(): () => void {
  const onClick = (event: MouseEvent) => {
    // Respect modifier-clicks and anything already handled.
    if (event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

    const anchor = (event.target as HTMLElement | null)?.closest?.("a");
    if (!anchor?.href) return;

    let url: URL;
    try {
      url = new URL(anchor.href, window.location.href);
    } catch {
      return;
    }
    if (!isExternal(url)) return;  // In-app routing stays with the router.

    event.preventDefault();

    const opened = window.open(url.href, "_blank", "noopener,noreferrer");
    if (!opened) {
      // WKWebView refused the popup — ask the shell instead.
      requestExternalOpen(url.href);
    }
  };

  document.addEventListener("click", onClick);
  return () => document.removeEventListener("click", onClick);
}
