"""Security tests for input hardening.

Port of tests/security/input.test.ts. Covers:
 - HTML sanitization: strips script/style/harmful content (XSS prevention)
 - URL parsing: blocks dangerous protocols, credential injection, SSRF-adjacent abuse
 - Title deduplication: immune to prefix injection tricks
 - Video URL extraction: no SSRF via malformed video URLs
"""

import socket as socket_module
from unittest.mock import patch
from urllib.parse import urlsplit

from app.lib.dedup.similarity import normalize_title_for_hash
from app.lib.integrations.content import is_blocked_ip, resolves_to_blocked_ip
from app.lib.utils.sanitize import extract_image_from_html, strip_html
from app.lib.utils.url import parse_http_url
from app.lib.utils.video import extract_video_info


class TestStripHtmlXssPrevention:
    def test_removes_script_open_close_tags(self):
        result = strip_html("Safe text <script>alert('xss')</script> more text")
        assert "<script>" not in result
        assert "</script>" not in result

    def test_removes_inline_event_handlers(self):
        result = strip_html('<p onclick="evil()">Click me</p>')
        assert "onclick" not in result
        assert result == "Click me"

    def test_removes_iframe_tags(self):
        result = strip_html('<iframe src="https://evil.com"></iframe>')
        assert "<iframe>" not in result
        assert "evil.com" not in result

    def test_removes_object_and_embed_tags(self):
        result = strip_html('<object data="payload.swf"></object>')
        assert "<object>" not in result

    def test_strips_all_tag_delimiters_from_nested_malicious_html(self):
        result = strip_html("<div><b><script>evil()</script></b></div>")
        assert "<div>" not in result
        assert "<script>" not in result
        assert "</script>" not in result
        assert "<" not in result

    def test_does_not_preserve_href_in_anchor_tags(self):
        result = strip_html('<a href="javascript:alert(1)">link</a>')
        assert "javascript:" not in result
        assert result == "link"

    def test_preserves_visible_text_content(self):
        result = strip_html("<p>Article text <b>with bold</b> and <em>emphasis</em>.</p>")
        assert result == "Article text with bold and emphasis."


class TestExtractImageFromHtmlSrcValues:
    def test_extracts_data_uri_src_without_validation(self):
        src = extract_image_from_html('<img src="data:image/png;base64,abc">')
        assert src is not None

    def test_parse_http_url_rejects_data_uris_extracted_from_img_tags(self):
        src = extract_image_from_html('<img src="data:image/png;base64,abc">')
        assert parse_http_url(src or "") is None

    def test_parse_http_url_accepts_normal_https_image_url(self):
        src = extract_image_from_html('<img src="https://cdn.example.com/photo.jpg">')
        assert parse_http_url(src or "") is not None


class TestParseHttpUrlProtocolEnforcement:
    def test_rejects_javascript_uris(self):
        assert parse_http_url("javascript:alert(document.cookie)") is None

    def test_rejects_vbscript_uris(self):
        assert parse_http_url("vbscript:MsgBox(1)") is None

    def test_rejects_file_uris(self):
        assert parse_http_url("file:///etc/passwd") is None

    def test_rejects_ftp_uris(self):
        assert parse_http_url("ftp://ftp.example.com/pub") is None

    def test_rejects_data_uris(self):
        assert parse_http_url("data:text/html,<script>evil()</script>") is None

    def test_accepts_https(self):
        assert parse_http_url("https://example.com") is not None

    def test_accepts_http(self):
        assert parse_http_url("http://example.com") is not None


class TestParseHttpUrlCredentialInjectionPrevention:
    def test_rejects_url_with_username_only(self):
        assert parse_http_url("https://attacker@example.com") is None

    def test_rejects_url_with_username_and_password(self):
        assert parse_http_url("https://admin:password@internal-server.com") is None

    def test_rejects_url_with_empty_username(self):
        assert parse_http_url("https://:password@example.com") is None


class TestParseHttpUrlSsrfAdjacentInputs:
    def test_parses_localhost_urls(self):
        result = parse_http_url("http://localhost/admin")
        assert result is not None
        assert urlsplit(result).hostname == "localhost"

    def test_parses_127_0_0_1_urls(self):
        result = parse_http_url("http://127.0.0.1:8080/")
        assert result is not None
        assert urlsplit(result).hostname == "127.0.0.1"

    def test_rejects_empty_string_input(self):
        assert parse_http_url("") is None

    def test_rejects_whitespace_only_input(self):
        assert parse_http_url("     ") is None


class TestIsBlockedIpLiteralChecks:
    def test_blocks_loopback_ipv4(self):
        assert is_blocked_ip("127.0.0.1") is True

    def test_blocks_private_ipv4_ranges(self):
        assert is_blocked_ip("10.0.0.5") is True
        assert is_blocked_ip("172.16.0.1") is True
        assert is_blocked_ip("192.168.1.1") is True

    def test_blocks_link_local_ipv4_including_cloud_metadata(self):
        assert is_blocked_ip("169.254.169.254") is True

    def test_blocks_loopback_ipv6(self):
        assert is_blocked_ip("::1") is True

    def test_allows_public_ipv4(self):
        assert is_blocked_ip("8.8.8.8") is False

    def test_fails_closed_on_unparseable_input(self):
        assert is_blocked_ip("not-an-ip") is True


class TestResolvesToBlockedIpHostnameGate:
    """Regression coverage for a bug where every hostname was blocked.

    ``resolves_to_blocked_ip`` used to call ``is_blocked_ip(hostname)``
    unconditionally as its "is this already an IP" check. For a real
    hostname, ``is_blocked_ip`` fails to parse it as an IP, swallows the
    exception, and fails closed (returns True) — so the function returned
    True for *every* non-IP hostname before ever reaching DNS resolution,
    silently blocking all legitimate fetches (fetch_article_content).
    """

    def test_blocks_known_blocked_hostnames_without_dns(self):
        assert resolves_to_blocked_ip("localhost") is True
        assert resolves_to_blocked_ip("0.0.0.0") is True

    def test_ip_literal_input_is_checked_directly(self):
        assert resolves_to_blocked_ip("127.0.0.1") is True
        assert resolves_to_blocked_ip("169.254.169.254") is True

    def test_allows_hostname_resolving_to_public_ip(self):
        with patch(
            "app.lib.integrations.content.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
        ):
            assert resolves_to_blocked_ip("example.com") is False

    def test_blocks_hostname_resolving_to_private_ip(self):
        with patch(
            "app.lib.integrations.content.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("10.0.0.5", 0))],
        ):
            assert resolves_to_blocked_ip("attacker-controlled-dns.example") is True

    def test_fails_closed_on_dns_resolution_failure(self):
        with patch(
            "app.lib.integrations.content.socket.getaddrinfo",
            side_effect=socket_module.gaierror("name resolution failed"),
        ):
            assert resolves_to_blocked_ip("this-host-does-not-exist.invalid") is True


class TestNormalizeTitleForHashPrefixInjectionResistance:
    def test_strips_recognized_news_prefixes_before_comparison(self):
        base = normalize_title_for_hash("War breaks out in region")
        with_prefix = normalize_title_for_hash("BREAKING: War breaks out in region")
        assert base == with_prefix

    def test_strips_exclusive_prefix(self):
        a = normalize_title_for_hash("Story about politics")
        b = normalize_title_for_hash("EXCLUSIVE: Story about politics")
        assert a == b

    def test_strips_live_prefix(self):
        a = normalize_title_for_hash("Coverage of summit")
        b = normalize_title_for_hash("LIVE: Coverage of summit")
        assert a == b

    def test_multiple_prefixes_still_match_base(self):
        a = normalize_title_for_hash("Election results announced")
        b = normalize_title_for_hash("ANALYSIS: Election results announced")
        assert a == b


class TestExtractVideoInfoEmbedUrlSafety:
    def test_embed_url_known_platform_domain_for_youtube(self):
        info = extract_video_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert info is not None
        assert info.embed_url.startswith("https://www.youtube.com/")

    def test_embed_url_known_platform_domain_for_vimeo(self):
        info = extract_video_info("https://vimeo.com/123456789")
        assert info is not None
        assert info.embed_url.startswith("https://player.vimeo.com/")

    def test_embed_url_known_platform_domain_for_dailymotion(self):
        info = extract_video_info("https://www.dailymotion.com/video/x7tgad2")
        assert info is not None
        assert info.embed_url.startswith("https://www.dailymotion.com/")

    def test_returns_none_for_malicious_path_looking_like_video_host(self):
        assert extract_video_info("https://vimeo.com/../../../etc/passwd") is None

    def test_returns_none_for_invalid_url(self):
        assert extract_video_info("javascript:void(0)") is None
