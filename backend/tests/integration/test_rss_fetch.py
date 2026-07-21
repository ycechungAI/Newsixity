"""Mocked-feed RSS ingestion test for app.lib.integrations.rss.

Exercises fetch_feed() against canned RSS/Atom XML with httpx.get mocked out,
so it never touches the network (safe for CI) while still asserting the exact
contract the Opus audit's bug fix depends on: fetch_feed must pass a real
timeout/User-Agent/follow_redirects to httpx (feedparser.parse() itself has no
timeout kwarg — that was the bug) and correctly parse the response bytes.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.lib.integrations.rss import (
    FEED_FETCH_TIMEOUT_SECONDS,
    FEED_USER_AGENT,
    ParsedArticle,
    fetch_feed,
)

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Sample Feed</title>
    <item>
      <title>First Article</title>
      <link>https://example.com/first</link>
      <guid>https://example.com/first</guid>
      <author>jane@example.com (Jane Doe)</author>
      <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
      <description>&lt;p&gt;Some &lt;b&gt;summary&lt;/b&gt; text.&lt;/p&gt;</description>
      <enclosure url="https://example.com/first.jpg" type="image/jpeg" />
    </item>
    <item>
      <title>Second Article</title>
      <link>https://example.com/second</link>
      <guid>https://example.com/second</guid>
      <description>Plain description, no image.</description>
    </item>
  </channel>
</rss>
"""


def _mock_response(content: bytes, status_code: int = 200):
    resp = MagicMock()
    resp.content = content
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    return resp


class TestFetchFeedParsing:
    def test_parses_articles_from_mocked_feed(self):
        with patch("app.lib.integrations.rss.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(SAMPLE_RSS.encode())

            articles = fetch_feed("https://example.com/feed.xml")

        assert len(articles) == 2
        assert all(isinstance(a, ParsedArticle) for a in articles)

        first = articles[0]
        assert first.title == "First Article"
        assert first.link == "https://example.com/first"
        assert first.guid == "https://example.com/first"
        assert first.author == "Jane Doe"
        assert "summary" in first.content
        assert first.image_url == "https://example.com/first.jpg"

    def test_second_article_has_no_image(self):
        with patch("app.lib.integrations.rss.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(SAMPLE_RSS.encode())
            articles = fetch_feed("https://example.com/feed.xml")

        assert articles[1].image_url is None

    def test_empty_feed_returns_empty_list(self):
        empty_rss = (
            '<?xml version="1.0"?><rss version="2.0"><channel>'
            "<title>Empty</title></channel></rss>"
        )
        with patch("app.lib.integrations.rss.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(empty_rss.encode())
            articles = fetch_feed("https://example.com/empty.xml")

        assert articles == []


class TestFetchFeedHttpxContract:
    """The core regression this test guards: feedparser.parse() has no
    `timeout` kwarg, so fetch_feed must fetch via httpx.get with an explicit
    timeout/User-Agent/follow_redirects, then hand feedparser raw bytes."""

    def test_calls_httpx_with_timeout_and_user_agent(self):
        with patch("app.lib.integrations.rss.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(SAMPLE_RSS.encode())

            fetch_feed("https://example.com/feed.xml")

            mock_get.assert_called_once()
            args, kwargs = mock_get.call_args
            assert args[0] == "https://example.com/feed.xml"
            assert kwargs["timeout"] == FEED_FETCH_TIMEOUT_SECONDS
            assert kwargs["follow_redirects"] is True
            assert kwargs["headers"]["User-Agent"] == FEED_USER_AGENT

    def test_raises_when_http_error(self):
        with patch("app.lib.integrations.rss.httpx.get") as mock_get:
            resp = _mock_response(b"", status_code=500)
            resp.raise_for_status.side_effect = RuntimeError("500 error")
            mock_get.return_value = resp

            with pytest.raises(RuntimeError):
                fetch_feed("https://example.com/broken.xml")

    def test_never_hits_real_network(self):
        """Guard against a regression that removes the mock and silently
        hits example.com for real during CI."""
        with patch("app.lib.integrations.rss.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(SAMPLE_RSS.encode())
            fetch_feed("https://example.com/feed.xml")
            assert mock_get.call_count == 1


class TestFetchAllFeedsSyncErrorHandling:
    """fetch_all_feeds_sync must degrade per-feed, not raise, on a single
    feed failure (mirrors production: 11/34 feeds fail upstream but the app
    still ingests the other 23)."""

    def test_single_feed_failure_does_not_abort_others(self):
        from app.lib.integrations import rss as rss_module

        class FakeFeed:
            def __init__(self, id_, url):
                self.id = id_
                self.url = url

        feeds = [FakeFeed(1, "https://good.example.com/feed.xml"), FakeFeed(2, "https://bad.example.com/feed.xml")]

        def fake_fetch_feed(url):
            if "bad" in url:
                raise RuntimeError("boom")
            return [
                ParsedArticle(
                    guid="g1",
                    title="Good Article",
                    link="https://good.example.com/a",
                    author=None,
                    published_at="2024-01-01T00:00:00",
                    content=None,
                    image_url=None,
                )
            ]

        with (
            patch("app.db.repository.get_enabled_feeds", return_value=feeds),
            patch.object(rss_module, "fetch_feed", side_effect=fake_fetch_feed),
            patch("app.db.repository.feeds.update_feed_last_fetched"),
            patch("app.db.repository.feeds.update_feed_last_error"),
        ):
            results = rss_module.fetch_all_feeds_sync()

        assert len(results) == 2
        good, bad = results
        assert good.error is None
        assert len(good.articles) == 1
        assert bad.error == "boom"
        assert bad.articles == []
