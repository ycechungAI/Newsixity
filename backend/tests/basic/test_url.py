"""Tests for URL utility functions (parse_http_url, is_http_url)."""

import pytest
from app.lib.utils.url import parse_http_url, is_http_url


class TestParseHttpUrl:
    """Tests for parse_http_url function."""

    def test_returns_url_for_valid_https_url(self):
        result = parse_http_url("https://example.com/path")
        assert result is not None
        assert result.startswith("https://example.com/path")

    def test_returns_url_for_valid_http_url(self):
        result = parse_http_url("http://example.com")
        assert result is not None
        assert result.startswith("http://example.com")

    def test_returns_none_for_null_input(self):
        assert parse_http_url(None) is None

    def test_returns_none_for_empty_string(self):
        assert parse_http_url("") is None

    def test_returns_none_for_whitespace_only_string(self):
        assert parse_http_url("   ") is None

    def test_trims_whitespace_before_parsing(self):
        result = parse_http_url("  https://example.com  ")
        assert result is not None
        assert "example.com" in result

    def test_returns_none_for_ftp_protocol(self):
        assert parse_http_url("ftp://files.example.com") is None

    def test_returns_none_for_file_protocol(self):
        assert parse_http_url("file:///etc/passwd") is None

    def test_returns_none_for_data_uri(self):
        assert parse_http_url("data:text/html,<h1>test</h1>") is None

    def test_returns_none_for_javascript_uri(self):
        assert parse_http_url("javascript:alert(1)") is None

    def test_returns_none_for_url_with_username(self):
        assert parse_http_url("https://user@example.com") is None

    def test_returns_none_for_url_with_credentials(self):
        assert parse_http_url("https://user:pass@example.com") is None

    def test_returns_none_for_malformed_url(self):
        assert parse_http_url("not a url") is None

    def test_preserves_query_parameters(self):
        result = parse_http_url("https://example.com/search?q=test&page=2")
        assert result is not None
        assert "q=test" in result
        assert "page=2" in result

    def test_preserves_url_path(self):
        result = parse_http_url("https://example.com/a/b/c")
        assert result is not None
        assert "/a/b/c" in result


class TestIsHttpUrl:
    """Tests for is_http_url function."""

    def test_returns_true_for_valid_https_url(self):
        assert is_http_url("https://example.com") is True

    def test_returns_true_for_valid_http_url(self):
        assert is_http_url("http://example.com") is True

    def test_returns_false_for_null(self):
        assert is_http_url(None) is False

    def test_returns_false_for_empty_string(self):
        assert is_http_url("") is False

    def test_returns_false_for_ftp(self):
        assert is_http_url("ftp://example.com") is False

    def test_returns_false_for_credential_bearing_urls(self):
        assert is_http_url("https://user:pass@example.com") is False

    def test_returns_false_for_javascript_uri(self):
        assert is_http_url("javascript:void(0)") is False
