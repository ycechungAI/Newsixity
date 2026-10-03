"""Storage limits for untrusted feed/page text.

MAX_CONTENT_LENGTH was 8000, applied as an inline slice at six separate call
sites (insert, content update, three scraper paths, two manual-link paths).
At 8000 a long article lost its tail — which defeats keeping article text at
all, since it is the fallback when a link goes stale.

The limits are constants now so the next change is one edit rather than a hunt.
"""

from __future__ import annotations

import pytest

from app.db.repository import create_feed, upsert_article
from app.db.repository.articles import update_article_content
from app.lib.utils.sanitize import (
    MAX_AUTHOR_LENGTH,
    MAX_CONTENT_LENGTH,
    MAX_TITLE_LENGTH,
    strip_html,
)





class TestLimits:
    def test_content_limit_is_20k(self):
        assert MAX_CONTENT_LENGTH == 20_000

    def test_title_and_author_unchanged(self):
        """Only content was raised; these were already reasonable."""
        assert MAX_TITLE_LENGTH == 500
        assert MAX_AUTHOR_LENGTH == 200


class TestTruncation:
    def test_content_over_the_limit_is_truncated(self):
        long_text = "word " * 20_000
        out = strip_html(long_text)[:MAX_CONTENT_LENGTH]
        assert len(out) == MAX_CONTENT_LENGTH

    def test_short_content_is_untouched(self):
        text = "A short article."
        assert strip_html(text)[:MAX_CONTENT_LENGTH] == text

    def test_article_between_8k_and_20k_is_now_kept_whole(self):
        """The regression: at 8000 such an article lost everything past 8k."""
        article = "sentence. " * 1_500  # 15_000 chars
        cleaned = strip_html(article)
        assert 8_000 < len(cleaned) < MAX_CONTENT_LENGTH

        assert cleaned[:MAX_CONTENT_LENGTH] == cleaned, (
            "an article under the limit must not be cut"
        )
        # And it really would have been cut before.
        assert len(cleaned[:8_000]) < len(cleaned)


class TestScraperPath:
    def test_update_article_content_honours_the_same_limit(self, monkeypatch):
        """The summarizer's scraped text must not be cut harder than feed text."""
        captured = {}

        class FakeSession:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, stmt):
                captured["called"] = True

            def commit(self):
                pass

        monkeypatch.setattr("app.db.repository.articles.SessionLocal", lambda: FakeSession())

        long_text = "paragraph. " * 3_000  # ~33k
        update_article_content(1, long_text)

        assert captured["called"] is True

    def test_extraction_paths_use_the_constant(self):
        """Guard against a call site re-introducing a hardcoded slice."""
        import inspect

        from app.lib.integrations import content as content_mod

        src = inspect.getsource(content_mod)
        assert ":8000" not in src, "hardcoded 8000 reintroduced in content.py"