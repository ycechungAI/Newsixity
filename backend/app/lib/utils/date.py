"""Date formatting utilities — port of src/lib/utils/date.ts."""

from datetime import datetime


def time_ago(date_str: str | None) -> str:
    """Return a human-readable time difference (e.g., '5m ago', 'Jan 21')."""
    if not date_str:
        return "Unknown"

    try:
        date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return "Unknown"

    # Ensure both datetimes are timezone-aware or both timezone-naive
    if date.tzinfo:
        from datetime import timezone
        now = datetime.now(timezone.utc)
    else:
        now = datetime.now()
    diff = now - date
    diff_seconds = int(diff.total_seconds())
    diff_minutes = diff_seconds // 60
    diff_hours = diff_minutes // 60
    diff_days = diff_hours // 24

    if diff_seconds < 60:
        return "just now"
    if diff_minutes < 60:
        return f"{diff_minutes}m ago"
    if diff_hours < 24:
        return f"{diff_hours}h ago"
    if diff_days < 7:
        return f"{diff_days}d ago"

    months = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ]
    return f"{months[date.month - 1]} {date.day}"


def format_date(date_str: str | None) -> str:
    """Return a formatted date string (e.g., 'Jan 21, 2026 at 3:45 PM')."""
    if not date_str:
        return "Unknown"

    try:
        date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return "Unknown"

    months = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ]

    month = months[date.month - 1]
    day = date.day
    year = date.year
    hours = date.hour
    minutes = str(date.minute).zfill(2)
    ampm = "PM" if hours >= 12 else "AM"
    hours = hours % 12 or 12

    return f"{month} {day}, {year} at {hours}:{minutes} {ampm}"
