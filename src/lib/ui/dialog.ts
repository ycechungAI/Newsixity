/**
 * In-app replacements for window.confirm / window.alert.
 *
 * Native JS dialogs do not work in the packaged desktop app. Tauri's
 * WKWebView has no handler wired for them, so `confirm()` returns false
 * without ever showing anything and `alert()` is a no-op. Every guarded
 * action therefore did nothing at all once installed — delete an article,
 * remove a stock, clear the summarization queue, create or restore a
 * backup — while working perfectly in a dev browser. That difference is
 * exactly what makes this class of bug so easy to ship.
 *
 * These are imperative and promise-based so they drop straight into the
 * existing call sites (`if (!confirm(...)) return;` becomes
 * `if (!(await confirmDialog(...))) return;`), with no provider to mount
 * and no state to thread through components.
 *
 * Deliberately plain DOM rather than React: this is called from event
 * handlers all over the app, including ones not inside a React tree, and a
 * portal would need a host component mounted at the root.
 */

const OVERLAY_CLASS = "app-dialog-overlay";

function buildDialog(
  message: string,
  opts: { confirmLabel: string; cancelLabel?: string; danger?: boolean }
): { overlay: HTMLDivElement; confirmBtn: HTMLButtonElement; cancelBtn: HTMLButtonElement | null } {
  const overlay = document.createElement("div");
  overlay.className = OVERLAY_CLASS;
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");

  const box = document.createElement("div");
  box.className = "app-dialog";

  const text = document.createElement("div");
  text.className = "app-dialog-text";
  // textContent, not innerHTML: messages include server error strings.
  text.textContent = message;
  box.appendChild(text);

  const row = document.createElement("div");
  row.className = "app-dialog-actions";

  let cancelBtn: HTMLButtonElement | null = null;
  if (opts.cancelLabel) {
    cancelBtn = document.createElement("button");
    cancelBtn.className = "app-dialog-btn";
    cancelBtn.textContent = opts.cancelLabel;
    row.appendChild(cancelBtn);
  }

  const confirmBtn = document.createElement("button");
  confirmBtn.className = `app-dialog-btn${opts.danger ? " is-danger" : " is-primary"}`;
  confirmBtn.textContent = opts.confirmLabel;
  row.appendChild(confirmBtn);

  box.appendChild(row);
  overlay.appendChild(box);
  return { overlay, confirmBtn, cancelBtn };
}

function present(
  message: string,
  opts: { confirmLabel: string; cancelLabel?: string; danger?: boolean }
): Promise<boolean> {
  return new Promise((resolve) => {
    const { overlay, confirmBtn, cancelBtn } = buildDialog(message, opts);

    const close = (result: boolean) => {
      window.removeEventListener("keydown", onKey);
      overlay.remove();
      resolve(result);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close(false);
      if (e.key === "Enter") close(true);
    };

    confirmBtn.addEventListener("click", () => close(true));
    cancelBtn?.addEventListener("click", () => close(false));
    // Click-outside cancels, matching the platform convention.
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) close(false);
    });
    window.addEventListener("keydown", onKey);

    document.body.appendChild(overlay);
    confirmBtn.focus();
  });
}

/** Replacement for window.confirm. Resolves true when confirmed. */
export function confirmDialog(
  message: string,
  opts: { confirmLabel?: string; danger?: boolean } = {}
): Promise<boolean> {
  return present(message, {
    confirmLabel: opts.confirmLabel ?? "Confirm",
    cancelLabel: "Cancel",
    danger: opts.danger,
  });
}

/** Replacement for window.alert. Resolves once dismissed. */
export function notify(message: string): Promise<boolean> {
  return present(message, { confirmLabel: "OK" });
}
