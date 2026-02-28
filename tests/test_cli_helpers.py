"""Tests for pure-logic helpers in cli.py."""

from __future__ import annotations

import pytest

from chaoscatcher.cli import _parse_minutes, _parse_tags, _sparkline

# ---- _parse_minutes ----


def test_parse_minutes_none():
    assert _parse_minutes(None, "--x") is None


def test_parse_minutes_plain_int():
    assert _parse_minutes("90", "--x") == 90


def test_parse_minutes_zero():
    assert _parse_minutes("0", "--x") == 0


def test_parse_minutes_hhmm():
    assert _parse_minutes("7:30", "--x") == 450


def test_parse_minutes_hhmm_zero_minutes():
    assert _parse_minutes("8:00", "--x") == 480


def test_parse_minutes_hm_both():
    assert _parse_minutes("1h30m", "--x") == 90


def test_parse_minutes_hours_only():
    assert _parse_minutes("7h", "--x") == 420


def test_parse_minutes_minutes_only():
    assert _parse_minutes("45m", "--x") == 45


def test_parse_minutes_bad_raises():
    with pytest.raises(SystemExit):
        _parse_minutes("abc", "--x")


def test_parse_minutes_bad_hhmm_raises():
    with pytest.raises(SystemExit):
        _parse_minutes("7:75", "--x")


# ---- _parse_tags ----


def test_parse_tags_none():
    assert _parse_tags(None) == []


def test_parse_tags_empty():
    assert _parse_tags("") == []


def test_parse_tags_single():
    assert _parse_tags("baseline") == ["baseline"]


def test_parse_tags_comma_separated():
    assert _parse_tags("baseline,school") == ["baseline", "school"]


def test_parse_tags_space_separated():
    assert _parse_tags("baseline school") == ["baseline", "school"]


def test_parse_tags_mixed():
    assert _parse_tags("baseline, school adhd") == ["baseline", "school", "adhd"]


def test_parse_tags_deduplicates():
    result = _parse_tags("baseline baseline BASELINE")
    assert result == ["baseline"]


def test_parse_tags_preserves_order():
    result = _parse_tags("c b a")
    assert result == ["c", "b", "a"]


# ---- _sparkline ----


def test_sparkline_empty():
    assert _sparkline([]) == ""


def test_sparkline_single():
    result = _sparkline([5.0])
    assert len(result) == 1


def test_sparkline_length_matches_input():
    result = _sparkline([1.0, 5.0, 10.0])
    assert len(result) == 3


def test_sparkline_min_is_lowest_block():
    result = _sparkline([1.0, 10.0])
    assert result[0] == "▁"
    assert result[1] == "█"


def test_sparkline_custom_range():
    result = _sparkline([0.0, 100.0], vmin=0.0, vmax=100.0)
    assert result[0] == "▁"
    assert result[1] == "█"
