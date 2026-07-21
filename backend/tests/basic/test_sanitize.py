"""Tests for sanitize utility functions."""

import pytest
from app.lib.utils.sanitize import strip_html, truncate, extract_image_from_html


class TestStripHtml:
    """Tests for strip_html function."""

    def test_removes_block_level_html_tags(self):
        assert strip_html("<p>Hello world</p>") == "Hello world"

    def test_removes_inline_html_tags(self):
        assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_decodes_amp(self):
        assert strip_html("&amp;") == "&"

    def test_decodes_lt_and_gt(self):
        assert strip_html("&lt;div&gt;") == "<div>"

    def test_decodes_quot(self):
        assert strip_html("&quot;hello&quot;") == '"hello"'

    def test_decodes_numeric_entity(self):
        assert strip_html("&#39;it&#39;s") == "'it's"

    def test_normalizes_internal_whitespace_to_single_space(self):
        assert strip_html("foo   bar") == "foo bar"

    def test_trims_leading_and_trailing_whitespace(self):
        assert strip_html("  hello  ") == "hello"

    def test_returns_empty_string_for_empty_input(self):
        assert strip_html("") == ""

    def test_returns_plain_text_unchanged(self):
        assert strip_html("plain text") == "plain text"

    def test_handles_nested_tags(self):
        assert strip_html("<div><span><em>deep</em></span></div>") == "deep"

    def test_handles_tags_with_attributes(self):
        assert (
            strip_html(
                '<a href="https://example.com" class="link">click</a>'
            )
            == "click"
        )


class TestTruncate:
    """Tests for truncate function."""

    def test_returns_original_text_when_shorter_than_max_length(self):
        assert truncate("hello", 10) == "hello"

    def test_returns_original_text_when_equal_to_max_length(self):
        assert truncate("hello", 5) == "hello"

    def test_truncates_long_text_and_appends_ellipsis(self):
        result = truncate("abcdefghijklmnopqrstuvwxyz", 10)
        assert result.endswith("...")

    def test_breaks_at_word_boundary_when_space_is_after_80_percent_mark(self):
        result = truncate("hello world test", 12)
        assert result == "hello world..."

    def test_returns_single_char_plus_ellipsis_for_tiny_max_length(self):
        result = truncate("hello world", 1)
        assert result == "h..."

    def test_hard_truncates_when_no_space_past_80_percent(self):
        result = truncate("foo bar baz", 9)
        assert result.endswith("...")
        assert len(result) <= 12  # 9 chars + "..."


class TestExtractImageFromHtml:
    """Tests for extract_image_from_html function."""

    def test_extracts_src_from_img_tag_with_double_quotes(self):
        assert (
            extract_image_from_html(
                '<img src="https://example.com/image.jpg" />'
            )
            == "https://example.com/image.jpg"
        )

    def test_extracts_src_from_img_tag_with_single_quotes(self):
        assert (
            extract_image_from_html("<img src='https://example.com/photo.png'>")
            == "https://example.com/photo.png"
        )

    def test_extracts_src_when_img_has_other_attributes_before_src(self):
        assert (
            extract_image_from_html(
                '<img alt="Photo" src="https://example.com/a.jpg">'
            )
            == "https://example.com/a.jpg"
        )

    def test_returns_none_when_there_is_no_img_tag(self):
        assert extract_image_from_html("<p>No image here</p>") is None

    def test_returns_none_for_empty_string(self):
        assert extract_image_from_html("") is None

    def test_returns_first_img_src_when_multiple_images_exist(self):
        assert (
            extract_image_from_html(
                '<img src="https://example.com/first.jpg"><img src="https://example.com/second.jpg">'
            )
            == "https://example.com/first.jpg"
        )
