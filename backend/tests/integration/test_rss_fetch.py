"""Mocked-feed RSS ingestion test for app.lib.integrations.rss.

Exercises fetch_feed() against canned RSS/Atom XML served by
httpx.MockTransport, so it never touches the network (safe for CI), and pins
the SSRF gate on every redirect hop (v0.4: feed URLs are user-supplied).
"""

from unittest.mock import patch

import httpx
import pytest

from app.lib.integrations.rss import (
    FEED_FETCH_TIMEOUT_SECONDS,
    FEED_USER_AGENT,
    MAX_FEED_REDIRECTS,
    ParsedArticle,
    UnsafeFeedUrlError,
    fetch_feed,
    probe_feed,
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


@pytest.fixture
def transport(monkeypatch):
    """Serve canned responses through httpx.MockTransport — never the network.

    ``routes`` maps URL -> (status, body, headers). DNS is stubbed too: the
    SSRF gate resolves hostnames, and example.com must not depend on a
    resolver in CI. Hostnames listed in ``blocked`` resolve "privately".
    """
    from app.lib.integrations import rss as rss_module

    state = {"routes": {}, "blocked": set(), "requests": []}

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        status, body, headers = state["routes"].get(str(request.url), (404, b"", {}))
        return httpx.Response(status, content=body, headers=headers)

    def client(timeout=FEED_FETCH_TIMEOUT_SECONDS):
        return httpx.Client(
            transport=httpx.MockTransport(handler),
            timeout=timeout,
            follow_redirects=False,
            headers={"User-Agent": FEED_USER_AGENT},
        )

    monkeypatch.setattr(rss_module, "_feed_client", client)
    from ipaddress import ip_address

    from app.lib.integrations.content import is_blocked_ip

    def fake_resolves_to_blocked_ip(host):
        try:
            ip_address(host)
        except ValueError:
            return host in state["blocked"]
        return is_blocked_ip(host)  # IP literals need no resolver

    monkeypatch.setattr(rss_module, "resolves_to_blocked_ip", fake_resolves_to_blocked_ip)
    return state


FEED_URL = "https://example.com/feed.xml"


class TestFetchFeedParsing:
    def test_parses_articles_from_mocked_feed(self, transport):
        transport["routes"][FEED_URL] = (200, SAMPLE_RSS.encode(), {})
        articles = fetch_feed(FEED_URL)

        assert len(articles) == 2
        assert all(isinstance(a, ParsedArticle) for a in articles)

        first = articles[0]
        assert first.title == "First Article"
        assert first.link == "https://example.com/first"
        assert first.guid == "https://example.com/first"
        assert first.author == "Jane Doe"
        assert "summary" in first.content
        assert first.image_url == "https://example.com/first.jpg"

    def test_second_article_has_no_image(self, transport):
        transport["routes"][FEED_URL] = (200, SAMPLE_RSS.encode(), {})
        assert fetch_feed(FEED_URL)[1].image_url is None

    def test_empty_feed_returns_empty_list(self, transport):
        empty_rss = (
            '<?xml version="1.0"?><rss version="2.0"><channel>'
            "<title>Empty</title></channel></rss>"
        )
        transport["routes"]["https://example.com/empty.xml"] = (200, empty_rss.encode(), {})
        assert fetch_feed("https://example.com/empty.xml") == []


class TestFetchFeedHttpContract:
    """feedparser.parse() has no `timeout` kwarg, so fetch_feed fetches the
    bytes itself with an explicit timeout/User-Agent, then hands feedparser
    raw bytes."""

    def test_sends_user_agent(self, transport):
        transport["routes"][FEED_URL] = (200, SAMPLE_RSS.encode(), {})
        fetch_feed(FEED_URL)
        assert transport["requests"][0].headers["User-Agent"] == FEED_USER_AGENT

    def test_raises_when_http_error(self, transport):
        transport["routes"]["https://example.com/broken.xml"] = (500, b"", {})
        with pytest.raises(httpx.HTTPStatusError):
            fetch_feed("https://example.com/broken.xml")

    def test_follows_a_public_redirect(self, transport):
        transport["routes"][FEED_URL] = (301, b"", {"location": "https://cdn.example.com/f.xml"})
        transport["routes"]["https://cdn.example.com/f.xml"] = (200, SAMPLE_RSS.encode(), {})
        assert len(fetch_feed(FEED_URL)) == 2


class TestFeedSsrfGate:
    """User-added feeds (v0.4) make feed URLs attacker-influenced."""

    def test_rejects_non_http_scheme(self, transport):
        with pytest.raises(UnsafeFeedUrlError):
            fetch_feed("file:///etc/passwd")
        assert transport["requests"] == []

    def test_rejects_host_resolving_privately(self, transport):
        transport["blocked"].add("intranet.example.com")
        with pytest.raises(UnsafeFeedUrlError):
            fetch_feed("https://intranet.example.com/feed")
        assert transport["requests"] == []

    def test_rejects_redirect_to_private_address(self, transport):
        transport["routes"][FEED_URL] = (302, b"", {"location": "http://127.0.0.1:8000/api/settings"})
        with pytest.raises(UnsafeFeedUrlError):
            fetch_feed(FEED_URL)
        # The first hop was fetched; the private hop never was.
        assert [str(r.url) for r in transport["requests"]] == [FEED_URL]

    def test_redirect_loop_is_bounded(self, transport):
        transport["routes"][FEED_URL] = (302, b"", {"location": FEED_URL})
        with pytest.raises(ValueError):
            fetch_feed(FEED_URL)
        assert len(transport["requests"]) == MAX_FEED_REDIRECTS + 1


class TestProbeFeed:
    def test_accepts_a_feed_and_reports_its_title(self, transport):
        transport["routes"][FEED_URL] = (200, SAMPLE_RSS.encode(), {})
        probe = probe_feed(FEED_URL)
        assert probe.title == "Sample Feed" and probe.entry_count == 2

    def test_rejects_an_html_page(self, transport):
        transport["routes"][FEED_URL] = (200, b"<html><body>hello</body></html>", {})
        with pytest.raises(ValueError, match="RSS or Atom"):
            probe_feed(FEED_URL)


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
