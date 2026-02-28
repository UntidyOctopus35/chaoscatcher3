"""Shared low-level helpers used by both cli.py and gui.py."""

from __future__ import annotations

from datetime import datetime


def _now_local() -> datetime:
    return datetime.now().astimezone()


def _fmt_time(dt: datetime) -> str:
    # Windows-safe formatting
    try:
        return dt.strftime("%-I:%M %p")
    except ValueError:
        return dt.strftime("%I:%M %p").lstrip("0")


def _dt_from_entry_ts(ts: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_now_local().tzinfo)
        return dt.astimezone()
    except Exception:
        return None
