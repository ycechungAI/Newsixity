"""Article text acquisition — the one place that decides whether to scrape.

Extracted from the summarizer because two callers need the same decision and
they had drifted apart:

* ``summarizer.summarize_one`` (the scheduled queue) fetched the original page
  when feed text was a teaser.
* ``routers/summarize`` (the article page's "Summarize" button) did not fetch
  at all — it summarized whatever sat in ``content``.

The result was the same article summarizing differently depending on how you
reached it. Both now call :func:`ensure_article_text`.

A third motivation: the queue only ever visits *unsummarized* articles, so
already-summarized ones kept their teaser text forever. Measured on this
install: 622 of 712 already-summarized articles were still teaser-length. That
is what ``backfill_full_text`` is for.
"""

from __future__ import annotations

import logging
from typing import NamedTuple

from app.db.repository import update_article_content
from app.db.repository.helpers import Article
from app.lib.integrations.content import fetch_article_content

logger = logging.getLogger("newsixity")

# Feed text shorter than this is treated as an excerpt, and the original page
# is fetched instead. Chosen against real feeds: stored content in this install
# averages ~197 chars and is almost entirely teaser length, while a scraped
# article body runs into the thousands. 1500 keeps genuinely short-but-complete
# posts (wire copy, small blogs) from being needlessly re-fetched.
TEASER_MAX_LENGTH = 1500

# A scrape is kept only if it is meaningfully better than what it replaces.
#
# The first version of this rule also demanded the result clear
# TEASER_MAX_LENGTH in absolute terms. That silently threw away good scrapes
# from sources whose posts are genuinely short: a Schneier blog entry stored
# 796 chars from the feed and scraped to 1037 — a 30% improvement, well over
# any sane gain threshold, but never reaching 1500, so it was rejected and
# re-attempted on every run forever.
#
# Now the comparison is purely relative, so a short post can still be improved
# while a partial extraction still cannot make things worse.
MIN_SCRAPE_GAIN_CHARS = 200
MIN_SCRAPE_GAIN_RATIO = 1.2


def scrape_is_better(fetched: str, existing: str | None) -> bool:
    """Whether a scrape is worth replacing existing text with.

    True when it is at least 200 characters longer *or* at least 20% longer,
    whichever is easier — so both short posts and long ones can improve, while
    a truncated or duplicate extraction cannot overwrite good data.
    """
    if not fetched:
        return False
    current = len(existing or "")
    if current == 0:
        return True
    return (len(fetched) - current >= MIN_SCRAPE_GAIN_CHARS) or (
        len(fetched) >= current * MIN_SCRAPE_GAIN_RATIO
    )


def needs_full_text(content: str | None) -> bool:
    """Whether stored text is too short to be a real article body."""
    return not content or len(content) < TEASER_MAX_LENGTH


class FullTextResult(NamedTuple):
    """What a full-text attempt actually did.

    The distinction in ``served`` is the reason this exists rather than a bare
    string return. "The stored text didn't change" is ambiguous: a paywalled
    source refuses and returns nothing, and an article that was *already*
    correct also doesn't change because the fetch came back identical. The
    backfill needs to tell those apart to decide whether a feed is blocking us.
    """

    text: str | None
    #: False only when a fetch was attempted and the source returned nothing.
    #: When no fetch was needed, True — absence of a refusal is not a refusal.
    served: bool
    #: Whether stored text was replaced with a better scrape.
    improved: bool


async def acquire_full_text(article: Article) -> FullTextResult:
    """Fetch and persist the page if the feed only gave a teaser.

    Persists anything it fetches via ``update_article_content`` so the scrape
    survives to the next run and to the full-text view on the article page.

    Never raises: a fetch failure leaves the existing text untouched, which may
    still be enough to summarize.
    """
    content = article.content

    if not needs_full_text(content) or not article.link:
        return FullTextResult(content, served=True, improved=False)

    try:
        fetched = await fetch_article_content(article.link)
    except Exception as exc:  # noqa: BLE001 — a failed fetch must not break summarizing
        logger.warning(
            "Full-text fetch failed for article %s (%s): %s",
            article.id,
            article.link,
            exc,
        )
        # An error is not the source refusing us; don't let it count against
        # the feed as a block.
        return FullTextResult(content, served=True, improved=False)

    if not fetched:
        return FullTextResult(content, served=False, improved=False)

    if not scrape_is_better(fetched, content):
        logger.info(
            "Full-text fetch for article %s returned %d chars, not better than the "
            "existing %d — keeping what we have",
            article.id,
            len(fetched),
            len(content or ""),
        )
        return FullTextResult(content, served=True, improved=False)

    update_article_content(article.id, fetched)
    article.content = fetched
    return FullTextResult(fetched, served=True, improved=True)


async def ensure_article_text(article: Article) -> str | None:
    """Return usable article text, fetching the page if the feed gave a teaser."""
    result = await acquire_full_text(article)
    return result.text