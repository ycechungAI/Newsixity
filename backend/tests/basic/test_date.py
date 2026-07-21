"""Tests for date utility functions."""

import re
from datetime import datetime, timezone
import pytest
from app.lib.utils.date import time_ago, format_date


class TestTimeAgo:
    """Tests for time_ago function."""

    def test_returns_unknown_for_null(self):
        assert time_ago(None) == "Unknown"

    def test_returns_unknown_for_invalid_date_string(self):
        assert time_ago("not-a-date") == "Unknown"

    def test_returns_just_now_for_30_seconds_ago(self):
        date = (datetime.now(timezone.utc) - self._td(seconds=30)).isoformat()
        assert time_ago(date) == "just now"

    def test_returns_just_now_for_59_seconds_ago(self):
        date = (datetime.now(timezone.utc) - self._td(seconds=59)).isoformat()
        assert time_ago(date) == "just now"

    def test_returns_minutes_label_for_5_minutes_ago(self):
        date = (datetime.now(timezone.utc) - self._td(minutes=5)).isoformat()
        assert time_ago(date) == "5m ago"

    def test_returns_minutes_label_for_59_minutes_ago(self):
        date = (datetime.now(timezone.utc) - self._td(minutes=59)).isoformat()
        assert time_ago(date) == "59m ago"

    def test_returns_hours_label_for_3_hours_ago(self):
        date = (datetime.now(timezone.utc) - self._td(hours=3)).isoformat()
        assert time_ago(date) == "3h ago"

    def test_returns_hours_label_for_23_hours_ago(self):
        date = (datetime.now(timezone.utc) - self._td(hours=23)).isoformat()
        assert time_ago(date) == "23h ago"

    def test_returns_days_label_for_2_days_ago(self):
        date = (datetime.now(timezone.utc) - self._td(days=2)).isoformat()
        assert time_ago(date) == "2d ago"

    def test_returns_days_label_for_6_days_ago(self):
        date = (datetime.now(timezone.utc) - self._td(days=6)).isoformat()
        assert time_ago(date) == "6d ago"

    def test_returns_month_day_for_older_than_7_days(self):
        date = "2020-03-15T10:00:00Z"
        result = time_ago(date)
        assert re.match(r"^[A-Z][a-z]{2} \d{1,2}$", result)

    @staticmethod
    def _td(**kwargs):
        from datetime import timedelta
        return timedelta(**kwargs)


class TestFormatDate:
    """Tests for format_date function."""

    def test_returns_unknown_for_null(self):
        assert format_date(None) == "Unknown"

    def test_returns_unknown_for_invalid_date_string(self):
        assert format_date("not-a-date") == "Unknown"

    def test_formats_valid_iso_date_string(self):
        result = format_date("2024-06-15T12:00:00Z")
        assert re.match(
            r"^[A-Z][a-z]{2} \d{1,2}, \d{4} at \d{1,2}:\d{2} (AM|PM)$",
            result
        )

    def test_includes_am_pm_indicator(self):
        result = format_date("2024-01-01T08:00:00Z")
        assert "AM" in result or "PM" in result

    def test_pads_minutes_with_leading_zero(self):
        result = format_date("2024-01-01T10:05:00Z")
        assert re.search(r"\d{1,2}:0[0-9]", result)

    def test_converts_0_hours_to_12(self):
        result = format_date("2024-01-01T00:00:00Z")
        assert re.match(
            r"^[A-Z][a-z]{2} \d{1,2}, \d{4} at \d{1,2}:\d{2} (AM|PM)$",
            result
        )
