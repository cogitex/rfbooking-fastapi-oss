# RFBooking FastAPI OSS - Self-hosted Equipment Booking System
# Copyright (C) 2025 Oleg Tokmakov
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Utility helper functions."""

import html
import re
import secrets
from datetime import datetime, date, time, timedelta
from typing import Optional


def generate_token(length: int = 32) -> str:
    """Generate a secure random token.

    Args:
        length: Length of the token in bytes (will be URL-safe encoded).

    Returns:
        URL-safe random token string.
    """
    return secrets.token_urlsafe(length)


def escape_html(text: Optional[str]) -> str:
    """Escape HTML special characters to prevent XSS.

    Args:
        text: Input text that may contain HTML.

    Returns:
        HTML-escaped string.
    """
    if text is None:
        return ""
    return html.escape(str(text))


def sanitize_input(text: Optional[str], max_length: Optional[int] = None) -> str:
    """Sanitize user input by stripping HTML tags and limiting length.

    Args:
        text: Input text to sanitize.
        max_length: Maximum allowed length (truncates if exceeded).

    Returns:
        Sanitized string.
    """
    if text is None:
        return ""

    # Remove HTML tags
    clean = re.sub(r"<[^>]+>", "", str(text))

    # Normalize whitespace
    clean = " ".join(clean.split())

    # Truncate if needed
    if max_length and len(clean) > max_length:
        clean = clean[:max_length]

    return clean


def is_valid_email(email: str) -> bool:
    """Validate email format.

    Args:
        email: Email address to validate.

    Returns:
        True if valid email format.
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def format_datetime(dt: Optional[datetime], fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime for display.

    Args:
        dt: Datetime to format.
        fmt: Format string.

    Returns:
        Formatted datetime string or empty string if None.
    """
    if dt is None:
        return ""
    return dt.strftime(fmt)


def format_date(d: Optional[date], fmt: str = "%Y-%m-%d") -> str:
    """Format date for display.

    Args:
        d: Date to format.
        fmt: Format string.

    Returns:
        Formatted date string or empty string if None.
    """
    if d is None:
        return ""
    return d.strftime(fmt)


def format_time(t: Optional[time], fmt: str = "%H:%M") -> str:
    """Format time for display.

    Args:
        t: Time to format.
        fmt: Format string.

    Returns:
        Formatted time string or empty string if None.
    """
    if t is None:
        return ""
    return t.strftime(fmt)


def is_weekend(d: date) -> bool:
    """Check if date is a weekend (Saturday or Sunday).

    Args:
        d: Date to check.

    Returns:
        True if weekend.
    """
    return d.weekday() >= 5  # 5 = Saturday, 6 = Sunday


def add_working_days(start_date: date, days: int) -> date:
    """Add working days (excluding weekends) to a date.

    Args:
        start_date: Starting date.
        days: Number of working days to add.

    Returns:
        Resulting date after adding working days.
    """
    if days == 0:
        return start_date

    current = start_date
    remaining = abs(days)
    direction = 1 if days > 0 else -1

    while remaining > 0:
        current += timedelta(days=direction)
        if not is_weekend(current):
            remaining -= 1

    return current


def parse_time_string(time_str: str) -> Optional[time]:
    """Parse time string in various formats.

    Args:
        time_str: Time string like "08:00", "8:00:00", "8am"

    Returns:
        time object or None if invalid.
    """
    if not time_str:
        return None

    # Try common formats
    formats = ["%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M%p", "%I%p"]

    for fmt in formats:
        try:
            return datetime.strptime(time_str.strip(), fmt).time()
        except ValueError:
            continue

    return None


def parse_date_string(date_str: str) -> Optional[date]:
    """Parse date string in various formats.

    Args:
        date_str: Date string like "2025-01-15", "01/15/2025"

    Returns:
        date object or None if invalid.
    """
    if not date_str:
        return None

    # Try common formats
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue

    return None


def get_date_range_days(start_date: date, end_date: date) -> int:
    """Get number of days in a date range (inclusive).

    Args:
        start_date: Start of range.
        end_date: End of range.

    Returns:
        Number of days.
    """
    return (end_date - start_date).days + 1


def get_working_days_in_range(start_date: date, end_date: date) -> int:
    """Count working days in a date range (inclusive).

    Args:
        start_date: Start of range.
        end_date: End of range.

    Returns:
        Number of working days.
    """
    count = 0
    current = start_date

    while current <= end_date:
        if not is_weekend(current):
            count += 1
        current += timedelta(days=1)

    return count
