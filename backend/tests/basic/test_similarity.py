"""Tests for similarity/dedup utility functions."""

import pytest
from app.lib.dedup.similarity import (
    normalize_title_for_hash,
    get_bigrams,
    bigram_similarity,
    is_duplicate,
)


class TestNormalizeTitleForHash:
    """Tests for normalize_title_for_hash function."""

    def test_lowercases_the_title(self):
        assert normalize_title_for_hash("HELLO WORLD") == "hello world"

    def test_strips_breaking_prefix(self):
        assert (
            normalize_title_for_hash("BREAKING: Something happened")
            == "something happened"
        )

    def test_strips_update_prefix(self):
        assert (
            normalize_title_for_hash("UPDATE: Story evolves")
            == "story evolves"
        )

    def test_strips_opinion_prefix(self):
        assert (
            normalize_title_for_hash("OPINION: My view") == "my view"
        )

    def test_strips_breaking_news_prefix(self):
        assert (
            normalize_title_for_hash("BREAKING NEWS: Major event")
            == "major event"
        )

    def test_strips_watch_prefix(self):
        assert (
            normalize_title_for_hash("WATCH: Video clip") == "video clip"
        )

    def test_removes_punctuation(self):
        assert (
            normalize_title_for_hash("Hello, world!") == "hello world"
        )

    def test_normalizes_multiple_spaces_to_one(self):
        assert normalize_title_for_hash("foo   bar") == "foo bar"

    def test_trims_leading_and_trailing_whitespace(self):
        assert normalize_title_for_hash("  hello  ") == "hello"

    def test_does_not_strip_non_news_prefix_content(self):
        result = normalize_title_for_hash("Tech company releases update")
        assert result == "tech company releases update"


class TestGetBigrams:
    """Tests for get_bigrams function."""

    def test_returns_correct_bigrams_for_simple_string(self):
        assert get_bigrams("abc") == ["ab", "bc"]

    def test_returns_empty_array_for_single_character(self):
        assert get_bigrams("a") == []

    def test_returns_empty_array_for_empty_string(self):
        assert get_bigrams("") == []

    def test_returns_one_bigram_for_two_characters(self):
        assert get_bigrams("hi") == ["hi"]

    def test_includes_space_containing_bigrams(self):
        bigrams = get_bigrams("a b")
        assert "a " in bigrams
        assert " b" in bigrams


class TestBigramSimilarity:
    """Tests for bigram_similarity function."""

    def test_returns_1_0_for_identical_strings(self):
        assert bigram_similarity("hello world", "hello world") == 1.0

    def test_returns_1_0_for_strings_that_normalize_to_same_value(self):
        assert (
            bigram_similarity(
                "BREAKING: story about elections",
                "story about elections"
            ) == 1.0
        )

    def test_returns_0_for_completely_unrelated_short_strings(self):
        assert bigram_similarity("ab", "cd") == 0.0

    def test_returns_high_score_for_near_duplicate_titles(self):
        score = bigram_similarity(
            "Trump signs executive order on immigration",
            "Trump signs executive order on immigration reform"
        )
        assert score > 0.8, f"Expected score > 0.8 but got {score}"

    def test_returns_low_score_for_unrelated_titles(self):
        score = bigram_similarity(
            "NBA finals game 7 results",
            "Stock market hits record high"
        )
        assert score < 0.3, f"Expected score < 0.3 but got {score}"

    def test_returns_0_when_string_too_short(self):
        assert bigram_similarity("a", "hello world") == 0.0


class TestIsDuplicate:
    """Tests for is_duplicate function."""

    def test_returns_true_for_identical_titles(self):
        assert (
            is_duplicate(
                "Breaking: War erupts in region",
                "Breaking: War erupts in region"
            ) is True
        )

    def test_returns_true_for_near_duplicate_titles_above_threshold(self):
        assert (
            is_duplicate(
                "Scientists discover new planet in solar system",
                "Scientists discover new planet in our solar system"
            ) is True
        )

    def test_returns_false_for_clearly_different_titles(self):
        assert (
            is_duplicate(
                "Local weather forecast for this week",
                "Tech giant announces record profits"
            ) is False
        )

    def test_respects_custom_threshold(self):
        similar = bigram_similarity(
            "Apple releases new iPhone model",
            "Apple releases new iPhone 16 model"
        )
        result = is_duplicate(
            "Apple releases new iPhone model",
            "Apple releases new iPhone 16 model",
            0.99
        )
        assert result == (similar >= 0.99)

    def test_returns_true_with_very_low_threshold(self):
        assert (
            is_duplicate("completely different", "nothing alike", 0.0) is True
        )
