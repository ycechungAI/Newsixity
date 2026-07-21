"""Tests for search utility functions."""

import pytest
from app.lib.utils.search import detect_search_engine, is_search_engine_url


class TestDetectSearchEngine:
    """Tests for detect_search_engine function."""

    def test_detects_google_with_q_param(self):
        result = detect_search_engine("https://www.google.com/search?q=test+query")
        assert result is not None
        assert result.engine.name == "Google"
        assert result.query == "test query"

    def test_detects_google_on_google_co_uk_returns_none(self):
        result = detect_search_engine("https://www.google.co.uk/search?q=hello")
        assert result is None

    def test_detects_bing_with_q_param(self):
        result = detect_search_engine("https://www.bing.com/search?q=typescript")
        assert result is not None
        assert result.engine.name == "Bing"
        assert result.query == "typescript"

    def test_detects_duckduckgo_with_q_param(self):
        result = detect_search_engine("https://duckduckgo.com/?q=privacy+browser")
        assert result is not None
        assert result.engine.name == "DuckDuckGo"
        assert result.query == "privacy browser"

    def test_detects_yahoo_search_with_p_param(self):
        result = detect_search_engine("https://search.yahoo.com/search?p=weather+forecast")
        assert result is not None
        assert result.engine.name == "Yahoo"
        assert result.query == "weather forecast"

    def test_detects_baidu_with_wd_param(self):
        result = detect_search_engine("https://www.baidu.com/s?wd=news")
        assert result is not None
        assert result.engine.name == "Baidu"
        assert result.query == "news"

    def test_detects_yandex_with_text_param(self):
        result = detect_search_engine("https://yandex.com/search/?text=hello")
        assert result is not None
        assert result.engine.name == "Yandex"
        assert result.query == "hello"

    def test_decodes_url_encoded_query_params(self):
        result = detect_search_engine(
            "https://www.google.com/search?q=hello%20world%21"
        )
        assert result is not None
        assert result.query == "hello world!"

    def test_returns_none_for_regular_website_url(self):
        assert detect_search_engine("https://example.com/article") is None

    def test_returns_none_for_search_engine_url_without_query_param(self):
        assert detect_search_engine("https://www.google.com/") is None

    def test_returns_none_for_invalid_url(self):
        assert detect_search_engine("not-a-url") is None

    def test_returns_none_for_empty_string(self):
        assert detect_search_engine("") is None


class TestIsSearchEngineUrl:
    """Tests for is_search_engine_url function."""

    def test_returns_true_for_google_search_url(self):
        assert is_search_engine_url("https://www.google.com/search?q=test") is True

    def test_returns_true_for_duckduckgo_search_url(self):
        assert is_search_engine_url("https://duckduckgo.com/?q=test") is True

    def test_returns_false_for_non_search_url(self):
        assert is_search_engine_url("https://github.com/") is False

    def test_returns_false_for_invalid_url(self):
        assert is_search_engine_url("garbage") is False
