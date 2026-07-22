"""Priority-ordered background summarization — port of
src/lib/ollama/background.ts + src/lib/ollama/scheduler.ts.

Summarizes unsummarized articles in priority order (saved > recently fetched >
category batches), stopping early if Ollama goes offline. A module-level
``_background_running`` flag reproduces Node's ``backgroundRunning`` guard so a
batch triggered by the RSS refresh never piles up on the 3-minute scheduler run
(both call ``background_summarize``). Because the guard check and the flag set
are both synchronous — no ``await`` between them — the single-threaded asyncio
loop gives the same mutual-exclusion Node's single thread does.
"""

from __future__ import annotations

import logging

from app.db.repository import (
    MAX_UNSUMMARIZED_QUEUE,
    cull_unsummarized_queue_to_limit,
    get_article_by_id,
    get_recent_unsummarized_articles,
    get_summarization_queue_count,
    get_summarize_category_priority,
    get_unsummarized_by_category,
    get_unsummarized_saved_articles,
    mark_stuck_unsummarized_timed_out,
    update_article_content,
    update_article_summary,
)
from app.db.repository.helpers import Article
from app.lib.integrations.content import fetch_article_content
from app.lib.integrations.ollama import (
    OllamaUnavailableError,
    is_ollama_available,
    summarize_article,
)
from app.lib.services.summarization import get_default_model

logger = logging.getLogger("newsixity")

# ANSI color codes for terminal output
COLORS = {
    "success": "\033[92m",    # Light green
    "warning": "\033[93m",    # Yellow
    "error": "\033[91m",      # Light red
    "reset": "\033[0m",       # Reset
}

# Tracks whether a background batch is already running so runs don't pile up.
_background_running = False


async def summarize_one(article: Article) -> bool:
    """Summarize a single article, returning True on success.

    If content is missing, fetches it from the original URL first; if still
    missing, marks the article skipped so it leaves the queue.
    """
    content = article.content

    # If no content from RSS, try fetching from the original URL.
    if (not content or len(content) <= 10) and article.link:
        logger.info(
            "[Newsixity] No RSS content for article %s, fetching from %s",
            article.id,
            article.link,
        )
        fetched = await fetch_article_content(article.link)
        if fetched and len(fetched) > 50:
            content = fetched
            update_article_content(article.id, fetched)

    # Still no content after trying — mark skipped to remove from the queue.
    if not content or len(content) <= 10:
        update_article_summary(article.id, "[No content to summarize]", "skipped")
        logger.info(
            f'{COLORS["warning"]}[Newsixity] Skipped article %s (no content): "%s..."{COLORS["reset"]}',
            article.id,
            article.title[:50],
        )
        return False

    logger.info("[Newsixity] Calling summarizeArticle for article %s...", article.id)
    summary = await summarize_article(article.title, content)
    logger.info("[Newsixity] Got summary for article %s, updating DB...", article.id)
    model_used = await get_default_model()
    update_article_summary(article.id, summary, model_used)

    logger.info(
        f'{COLORS["success"]}[Newsixity] Summarized article %s: "%s..."{COLORS["reset"]}', article.id, article.title[:50]
    )
    return True


async def _process_batch(articles: list[Article], label: str, errors: list[str]) -> int:
    """Process a batch of articles. Returns count summarized.

    Raises OllamaUnavailableError if Ollama goes offline (caller should stop).
    """
    if not articles:
        return 0

    logger.info(
        "[Newsixity] Summarizing batch [%s]: %d articles", label, len(articles)
    )

    count = 0
    for article in articles:
        # Newly saved articles jump the queue — check between each article.
        urgent = get_unsummarized_saved_articles(1)
        if urgent and label != "saved":
            try:
                if await summarize_one(urgent[0]):
                    count += 1
            except OllamaUnavailableError:
                raise
            except Exception as e:  # noqa: BLE001
                error_msg = str(e)
                logger.error(
                    f'{COLORS["error"]}[Newsixity] ERROR summarizing urgent article %s: %s{COLORS["reset"]}', urgent[0].id, error_msg
                )
                errors.append(f"Article {urgent[0].id}: {error_msg}")
                # Mark failed to prevent an infinite retry loop.
                update_article_summary(
                    urgent[0].id,
                    f"[Summarization failed: {error_msg[:100]}]",
                    "error",
                )

        try:
            if await summarize_one(article):
                count += 1
        except OllamaUnavailableError:
            raise
        except Exception as e:  # noqa: BLE001
            error_msg = str(e)
            logger.error(
                f'{COLORS["error"]}[Newsixity] ERROR summarizing article %s: %s{COLORS["reset"]}', article.id, error_msg
            )
            errors.append(f"Article {article.id}: {error_msg}")
            update_article_summary(
                article.id,
                f"[Summarization failed: {error_msg[:100]}]",
                "error",
            )

    return count


async def background_summarize(limit: int = 10) -> dict:
    """Summarize unsummarized articles in priority order.

    Priority: (1) saved articles (always top, re-checked between batches),
    (2) recently fetched (< 20 min), (3) category batches in priority order.
    Stops early if Ollama goes offline. Returns {"summarized": int, "errors": []}.
    """
    global _background_running

    if _background_running:
        return {"summarized": 0, "errors": ["Background summarization already in progress"]}

    # If the queue is over the cap, cull oldest non-favourited first (so
    # refresh-triggered runs also respect the cap). All synchronous, matching
    # Node — no await before the running-flag is set.
    queue_count = get_summarization_queue_count()
    if queue_count > MAX_UNSUMMARIZED_QUEUE:
        culled = cull_unsummarized_queue_to_limit(MAX_UNSUMMARIZED_QUEUE)
        logger.info(
            "[Newsixity] Queue was %d, culled %d oldest non-favourited to %d",
            queue_count,
            culled,
            MAX_UNSUMMARIZED_QUEUE,
        )

    _background_running = True
    batch_size = max(1, min(100, limit))
    summarized = 0
    errors: list[str] = []

    # Clear stuck tasks older than 2 hours before processing.
    mark_stuck_unsummarized_timed_out()

    try:
        if not await is_ollama_available():
            return {"summarized": 0, "errors": ["Ollama is not available"]}

        # --- Priority 1: Saved articles ---
        saved = get_unsummarized_saved_articles(batch_size)
        if saved:
            summarized += await _process_batch(saved, "saved", errors)

        # --- Priority 2: Recently fetched (from the latest refresh) ---
        recent = get_recent_unsummarized_articles(20, batch_size)
        if recent:
            saved_ids = {s.id for s in saved}
            recent_filtered = [a for a in recent if a.id not in saved_ids]
            if recent_filtered:
                urgent_saved = get_unsummarized_saved_articles(batch_size)
                if urgent_saved:
                    summarized += await _process_batch(urgent_saved, "saved (urgent)", errors)
                summarized += await _process_batch(recent_filtered, "recent", errors)

        # --- Priority 3: Category batches in priority order ---
        category_priority = get_summarize_category_priority()
        more_work = True

        while more_work:
            more_work = False

            urgent_saved = get_unsummarized_saved_articles(batch_size)
            if urgent_saved:
                summarized += await _process_batch(urgent_saved, "saved (between rounds)", errors)

            fresh_recent = get_recent_unsummarized_articles(20, batch_size)
            if fresh_recent:
                summarized += await _process_batch(fresh_recent, "recent (between rounds)", errors)

            for slug in category_priority:
                batch = get_unsummarized_by_category(slug, batch_size)
                if not batch:
                    continue

                more_work = True
                summarized += await _process_batch(batch, slug, errors)

                mid_saved = get_unsummarized_saved_articles(batch_size)
                if mid_saved:
                    summarized += await _process_batch(mid_saved, "saved (mid-round)", errors)

        logger.info(
            "[Newsixity] Background summarize done: %d summarized, %d errors",
            summarized,
            len(errors),
        )
        if errors:
            logger.error("[Newsixity] Errors during summarization: %s", errors)
    except OllamaUnavailableError:
        logger.warning("[Newsixity] Ollama went offline, stopping background batch")
        errors.append("Ollama became unavailable")
    except Exception as e:  # noqa: BLE001
        errors.append(str(e))
    finally:
        _background_running = False

    return {"summarized": summarized, "errors": errors}


async def summarize_article_by_id(article_id: int) -> None:
    """Summarize a single article by ID (fire-and-forget).

    Used when a user saves an article to queue it immediately.
    """
    try:
        article = get_article_by_id(article_id)
        if not article:
            return

        # Already has a summary.
        if article.summary:
            return

        # No content to summarize.
        if not article.content or len(article.content) <= 10:
            return

        if not await is_ollama_available():
            return

        summary = await summarize_article(article.title, article.content)
        model_used = await get_default_model()
        update_article_summary(article_id, summary, model_used)

        logger.info(
            '[Newsixity] On-demand summarized article %s: "%s..."',
            article_id,
            article.title[:50],
        )
    except Exception as e:  # noqa: BLE001 — fire-and-forget, just log.
        logger.warning("[Newsixity] Failed to summarize article %s: %s", article_id, e)


async def check_and_summarize() -> None:
    """Scheduler entry: cull if over cap, then run the background summarizer.

    Port of checkAndSummarize in ollama/scheduler.ts.
    """
    try:
        queue_count = get_summarization_queue_count()

        if queue_count == 0:
            return  # Nothing to do.

        if queue_count > MAX_UNSUMMARIZED_QUEUE:
            logger.info(
                "[Newsixity] Summarization queue over limit (%d > %d), culling oldest non-favourited...",
                queue_count,
                MAX_UNSUMMARIZED_QUEUE,
            )
            culled = cull_unsummarized_queue_to_limit(MAX_UNSUMMARIZED_QUEUE)
            queue_count = get_summarization_queue_count()
            logger.info(
                "[Newsixity] Culled %d articles; queue now %d", culled, queue_count
            )

        logger.info(
            "[Newsixity] Summarization check: %d articles in queue", queue_count
        )

        await background_summarize()
    except Exception as e:  # noqa: BLE001
        logger.error("[Newsixity] Summarization scheduler error: %s", e)
