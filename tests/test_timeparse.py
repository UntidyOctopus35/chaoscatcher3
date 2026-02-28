"""Tests for timeparse.parse_ts."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

import pytest

from chaoscatcher.timeparse import parse_ts


def _is_iso(s: str) -> bool:
    """Check that the string looks like an ISO 8601 datetime with timezone."""
    return bool(re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}", s))


def _parse(s: str) -> datetime:
    return datetime.fromisoformat(parse_ts(s))


# ---- None / blank ----


def test_none_returns_now():
    before = datetime.now().astimezone().replace(microsecond=0)
    result = _parse(None)
    after = datetime.now().astimezone().replace(microsecond=0)
    assert before <= result <= after


def test_blank_returns_now():
    before = datetime.now().astimezone().replace(microsecond=0)
    result = _parse("  ")
    after = datetime.now().astimezone().replace(microsecond=0)
    assert before <= result <= after


# ---- ISO 8601 ----


def test_iso_with_timezone():
    result = parse_ts("2026-02-25T07:34:00-05:00")
    assert result.startswith("2026-02-25T07:34:00")


def test_iso_naive_assumed_local():
    result = _parse("2026-02-25T07:34:00")
    assert result.year == 2026
    assert result.month == 2
    assert result.day == 25
    assert result.hour == 7
    assert result.minute == 34
    assert result.tzinfo is not None


# ---- Relative ----


def test_relative_days_ago():
    result = _parse("3 days ago")
    expected = datetime.now().astimezone() - timedelta(days=3)
    assert abs((result - expected).total_seconds()) < 5


def test_relative_hours_ago():
    result = _parse("2 hours ago")
    expected = datetime.now().astimezone() - timedelta(hours=2)
    assert abs((result - expected).total_seconds()) < 5


def test_relative_minutes_ago():
    result = _parse("15 minutes ago")
    expected = datetime.now().astimezone() - timedelta(minutes=15)
    assert abs((result - expected).total_seconds()) < 5


def test_relative_1_day_ago():
    result = _parse("1 day ago")
    expected = datetime.now().astimezone() - timedelta(days=1)
    assert abs((result - expected).total_seconds()) < 5


# ---- Keyword date prefix ----


def test_today_with_time():
    result = _parse("today 9am")
    now = datetime.now().astimezone()
    assert result.date() == now.date()
    assert result.hour == 9
    assert result.minute == 0


def test_yesterday_with_time():
    result = _parse("yesterday 9am")
    expected_date = (datetime.now().astimezone() - timedelta(days=1)).date()
    assert result.date() == expected_date
    assert result.hour == 9


def test_tomorrow_with_time():
    result = _parse("tomorrow 7pm")
    expected_date = (datetime.now().astimezone() + timedelta(days=1)).date()
    assert result.date() == expected_date
    assert result.hour == 19


# ---- Time-only (assumes today) ----


def test_time_only_hhmm_ampm():
    result = _parse("7:34am")
    now = datetime.now().astimezone()
    assert result.date() == now.date()
    assert result.hour == 7
    assert result.minute == 34


def test_time_only_24h():
    result = _parse("14:30")
    now = datetime.now().astimezone()
    assert result.date() == now.date()
    assert result.hour == 14
    assert result.minute == 30


def test_time_only_hour_only():
    result = _parse("9am")
    now = datetime.now().astimezone()
    assert result.date() == now.date()
    assert result.hour == 9


# ---- Date + time formats ----


def test_date_plus_time_24h():
    result = _parse("2026-02-25 14:30")
    assert result.year == 2026
    assert result.month == 2
    assert result.day == 25
    assert result.hour == 14
    assert result.minute == 30


def test_date_plus_time_ampm():
    result = _parse("2026-02-25 7:34am")
    assert result.hour == 7
    assert result.minute == 34


# ---- Return format ----


def test_returns_iso_string_with_tz():
    result = parse_ts("2026-02-25T07:34:00-05:00")
    assert _is_iso(result)


# ---- Invalid input ----


def test_invalid_raises():
    with pytest.raises((SystemExit, ValueError)):
        parse_ts("not a time at all blah blah")
