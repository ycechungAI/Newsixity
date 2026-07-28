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
 * null do we fall back to a top-level navigation, which the Rust handler
 * then cancels and opens externally. So the browser keeps its new tab, the
 * packaged app opens the system browser, and neither needs to know which
 * one it is.
 */

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
      // WKWebView refused the popup. Navigating top-level reaches the Rust
      // on_navigation handler, which opens the system browser and cancels
      // the navigation — so the app itself never actually leaves the page.
      window.location.href = url.href;
    }
  };

  document.addEventListener("click", onClick);
  return () => document.removeEventListener("click", onClick);
}
