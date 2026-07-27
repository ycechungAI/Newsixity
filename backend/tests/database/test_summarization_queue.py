"""Tests for the "which articles still need summarizing" queue.

Regression coverage for a bug that silently stalled summarization: an Ollama
model can return an empty string (e.g. a reply that is entirely a <think>
block, stripped to nothing). That was stored as summary='', which is not
NULL — so the queue's ``summary IS NULL`` filter treated the article as
finished and never retried it. The Console reported "All caught up" while
real articles sat unsummarized indefinitely.

Fixture approach mirrors test_search_fts5.py: a real temp on-disk DB with
app.db.repository.articles.SessionLocal monkeypatched onto the module (it
binds the name via `from ... import SessionLocal`, so patching app.db.session
would not take effect).
"""

import app.db.repository.articles as articles_module
import pytest
from app.db.models import Article, Base, Category, Feed
from app.db.repository.articles import (
    get_unsummarized_articles,
    update_article_summary,
)
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def session_factory(tmp_path, monkeypatch):
    db_path = tmp_path / "queue_test.db"
    eng = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}, future=True
    )

    def enable_fk(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    event.listen(eng, "connect", enable_fk)
    Base.metadata.create_all(eng)
    factory = sessionmaker(bind=eng, autoflush=False, autocommit=False, future=True)
    monkeypatch.setattr(articles_module, "SessionLocal", factory)
    return factory


def _seed(factory, summaries: list[str | None]) -> list[int]:
    """Create one article per entry, with that entry as its summary."""
    ids = []
    with factory() as s:
        cat = Category(name="World", slug="world")
        s.add(cat)
        s.flush()
        feed = Feed(name="Test Feed", url="https://example.com/f.xml", category_id=cat.id)
        s.add(feed)
        s.flush()
        for i, summary in enumerate(summaries):
            a = Article(
                feed_id=feed.id,
                guid=f"guid-{i}",
                title=f"Article {i}",
                link=f"https://example.com/{i}",
                content="body text",
                summary=summary,
                published_at="2026-07-27T00:00:00.000Z",
            )
            s.add(a)
            s.flush()
            ids.append(a.id)
        s.commit()
    return ids


class TestUnsummarizedQueue:
    def test_null_summary_is_queued(self, session_factory):
        _seed(session_factory, [None])
        assert len(get_unsummarized_articles(limit=10)) == 1

    def test_empty_string_summary_is_queued(self, session_factory):
        """The actual bug: '' is not NULL, so it used to be skipped forever."""
        _seed(session_factory, [""])
        queued = get_unsummarized_articles(limit=10)
        assert len(queued) == 1, (
            "an article whose summary is an empty string must still be queued; "
            "otherwise a model that returns nothing strands it permanently"
        )

    def test_whitespace_only_summary_is_not_treated_as_done(self, session_factory):
        """Guarded at the write path, so it should never reach the DB at all."""
        ids = _seed(session_factory, [None])
        with pytest.raises(ValueError):
            update_article_summary(ids[0], "   \n  ", "some-model")

    def test_real_summary_is_not_queued(self, session_factory):
        _seed(session_factory, ["A genuine summary."])
        assert get_unsummarized_articles(limit=10) == []

    def test_placeholder_markers_are_not_requeued(self, session_factory):
        """Bracketed markers are a deliberate terminal state, not a gap.

        They stay out of the queue so a permanently-unsummarizable article
        does not loop forever; reset_failed_and_skipped_articles() is the
        explicit way to retry them.
        """
        _seed(
            session_factory,
            ["[No content to summarize]", "[Summarization failed: boom]"],
        )
        assert get_unsummarized_articles(limit=10) == []

    def test_mixed_batch_returns_only_the_gaps(self, session_factory):
        _seed(session_factory, ["done", None, "", "also done"])
        titles = {a.title for a in get_unsummarized_articles(limit=10)}
        assert titles == {"Article 1", "Article 2"}


class TestUpdateArticleSummaryGuard:
    def test_rejects_empty_summary(self, session_factory):
        ids = _seed(session_factory, [None])
        with pytest.raises(ValueError, match="empty summary"):
            update_article_summary(ids[0], "", "qwen3:8b")

    def test_rejects_none_summary(self, session_factory):
        ids = _seed(session_factory, [None])
        with pytest.raises(ValueError):
            update_article_summary(ids[0], None, "qwen3:8b")

    def test_leaves_the_row_untouched_when_it_refuses(self, session_factory):
        """A refused write must not partially apply — the article stays queued."""
        ids = _seed(session_factory, [None])
        with pytest.raises(ValueError):
            update_article_summary(ids[0], "", "qwen3:8b")
        assert len(get_unsummarized_articles(limit=10)) == 1

    def test_accepts_a_normal_summary(self, session_factory):
        ids = _seed(session_factory, [None])
        update_article_summary(ids[0], "Real summary.", "llama3.2:3b")
        assert get_unsummarized_articles(limit=10) == []
