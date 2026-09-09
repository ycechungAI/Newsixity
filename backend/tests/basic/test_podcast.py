"""Tests for the podcast parser's date normalization and episode ordering.

Regression guard for the "podcast episodes appear in wrong order" bug:
``published_at`` was stored as a raw RFC822 string (e.g. "Wed, 9 Sep 2020
09:56:18 +0000"), which sorts lexicographically by day-of-month and scrambles
``ORDER BY published_at DESC`` ordering.
"""

from datetime import timezone
from email.utils import parsedate_to_datetime

import pytest

from app.lib.podcast.parser import (
    extract_podcast_episodes,
    parse_duration_seconds,
)


def make_entry(published_rfc822: str, **overrides) -> dict:
    """Build a feedparser-style entry with both the raw string and parsed struct."""
    parsed = parsedate_to_datetime(published_rfc822).astimezone(timezone.utc)
    import time as _time

    return {
        "title": "Episode",
        "id": "guid-1",
        "published": published_rfc822,
        "published_parsed": parsed.timetuple(),
        "enclosures": [{"href": "https://cdn.example.com/ep1.mp3"}],
        "itunes_duration": "45:30",
        **overrides,
    }


class TestExtractPodcastEpisodesDateNormalization:
    """Episodes must get ISO-8601 published_at so SQL ORDER BY works."""

    def test_rfc822_date_is_normalized_to_iso(self):
        entries = [
            make_entry("Wed, 9 Sep 2020 09:56:18 +0000"),
            make_entry("Mon, 1 Mar 2026 10:00:00 +0000"),
        ]
        episodes = extract_podcast_episodes({"entries": entries})
        dates = [e["published_at"] for e in episodes]

        assert dates[0] == "2020-09-09T09:56:18+00:00"
        assert dates[1].startswith("2026-03-01T10:00:00")
        # Chronologically-correct ISO strings must sort oldest first when asked
        # to sort newest-first (i.e. isoformat sorts in the right direction).
        assert dates != episodes  # sanity: entries are 2020 then 2026
        sorted_newest_first = sorted(dates, reverse=True)
        assert sorted_newest_first[0].startswith("2026-03-01")  # newest first

    def test_no_published_parsed_falls_back_to_raw_string(self):
        entries = [{"title": "E", "id": "x", "enclosures": [{"href": "https://a/x.mp3"}]}]
        episodes = extract_podcast_episodes({"entries": entries})
        assert episodes[0]["published_at"] is None

    def test_skips_entry_without_audio(self):
        entries = [{"title": "No audio", "id": "x"}]
        assert extract_podcast_episodes({"entries": entries}) == []


class TestParseDurationSeconds:
    """itunes:duration parsing for podcast episodes."""

    def test_seconds_only(self):
        assert parse_duration_seconds("2700") == 2700

    def test_minutes_colon_seconds(self):
        assert parse_duration_seconds("45:30") == 45 * 60 + 30

    def test_hours_minutes_seconds(self):
        assert parse_duration_seconds("1:02:03") == 1 * 3600 + 2 * 60 + 3

    def test_invalid_returns_none(self):
        assert parse_duration_seconds("not-a-duration") is None
        assert parse_duration_seconds(None) is None
        assert parse_duration_seconds("") is None


@pytest.mark.parametrize(
    "rfc822,expected_prefix",
    [
        ("Wed, 9 Sep 2020 09:56:18 +0000", "2020-09-09T09:56:18+00:00"),
        ("Fri, 01 Mar 2026 00:00:00 +0000", "2026-03-01T00:00:00+00:00"),
        ("01 Mar 2026 10:00:00 +0000", "2026-03-01T10:00:00+00:00"),
    ],
)
def test_rfc822_variants_normalize_to_iso(rfc822: str, expected_prefix: str):
    episodes = extract_podcast_episodes({"entries": [make_entry(rfc822)]})
    assert episodes[0]["published_at"].startswith(expected_prefix)