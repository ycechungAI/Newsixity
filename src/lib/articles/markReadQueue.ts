// Module-level queue shared by every ArticleCard instance. Each card used to
// fire its own PATCH /api/articles/{id} when its IntersectionObserver
// decided the article had been read; a long list produced a burst of
// sequential single-article round trips. This batches every article that
// crosses the read threshold within a short window into one bulk
// PATCH /api/articles call.

const FLUSH_DELAY_MS = 400;

const pending = new Map<number, Array<(categorySlug: string | null) => void>>();
let flushTimer: ReturnType<typeof setTimeout> | null = null;

async function flush() {
  flushTimer = null;
  if (pending.size === 0) return;

  const batch = new Map(pending);
  pending.clear();
  const articleIds = Array.from(batch.keys());

  try {
    const res = await fetch("/api/articles", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ article_ids: articleIds }),
    });
    if (!res.ok) throw new Error("bulk mark-read failed");
    const data = await res.json();
    const slugById = new Map<number, string | null>(
      (data.updated as Array<{ id: number; categorySlug: string | null }>).map((u) => [
        u.id,
        u.categorySlug,
      ])
    );
    for (const [id, callbacks] of batch) {
      const slug = slugById.get(id) ?? null;
      callbacks.forEach((cb) => cb(slug));
    }
  } catch {
    // Best-effort, matching the prior per-card try/catch: a failed
    // mark-read is silently dropped rather than surfaced to the user.
  }
}

/** Queue an article for the next batched mark-read flush. Resolves with the
 * article's categorySlug once the batch completes (or null on failure). */
export function enqueueMarkRead(articleId: number): Promise<string | null> {
  return new Promise((resolve) => {
    const callbacks = pending.get(articleId) ?? [];
    callbacks.push(resolve);
    pending.set(articleId, callbacks);
    if (!flushTimer) flushTimer = setTimeout(flush, FLUSH_DELAY_MS);
  });
}
