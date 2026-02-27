from __future__ import annotations

import re
from datetime import datetime, timedelta


def _now_local() -> datetime:
    return datetime.now().astimezone()


def _with_local_tz(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_now_local().tzinfo)
    return dt.astimezone()


def parse_ts(value: str | None) -> str:
    """
    Parse flexible user time into ISO 8601 with local timezone.
    Accepts:
      - None -> now
      - ISO 8601 (with or without tz; naive assumed local)
      - "7:34am", "7:34 am", "19:34", "7am"
      - "2026-02-25 7:34am", "2026-02-25 19:34"
      - relative: "3 days ago", "1 day ago", "2 hours ago", "15 minutes ago"
      - keywords: "today 14:30", "yesterday 9am", "tomorrow 7pm"
    Returns: ISO string with local timezone, seconds precision.
    """
    if not value or not value.strip():
        return _now_local().isoformat(timespec="seconds")

    s = value.strip().lower()

    # --- 1) ISO 8601 ---
    try:
        dt = datetime.fromisoformat(value.strip())
        dt = _with_local_tz(dt)
        return dt.isoformat(timespec="seconds")
    except ValueError:
        pass

    now = _now_local()

    # --- 2) Relative like "3 days ago", "2 hours ago", "15 minutes ago" ---
    m = re.fullmatch(r"(\d+)\s*(day|days|hour|hours|minute|minutes)\s*ago", s)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if "day" in unit:
            dt = now - timedelta(days=n)
        elif "hour" in unit:
            dt = now - timedelta(hours=n)
        else:
            dt = now - timedelta(minutes=n)
        return dt.isoformat(timespec="seconds")

    # --- 3) Keyword date prefix: today/yesterday/tomorrow ---
    # Examples: "yesterday 9am", "today 14:30"
    m = re.fullmatch(r"(today|yesterday|tomorrow)\s+(.+)", s)
    if m:
        dayword = m.group(1)
        rest = m.group(2).strip()

        base = now
        if dayword == "yesterday":
            base = now - timedelta(days=1)
        elif dayword == "tomorrow":
            base = now + timedelta(days=1)

        dt_time = _parse_time_only(rest, base)
        return dt_time.isoformat(timespec="seconds")

    # --- 4) Date + time formats ---
    dt_formats = [
        "%Y-%m-%d %I:%M%p",
        "%Y-%m-%d %I:%M %p",
        "%Y-%m-%d %I%p",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %I:%M%p",
        "%Y/%m/%d %I:%M %p",
        "%Y/%m/%d %H:%M",
    ]
    for fmt in dt_formats:
        try:
            dt = datetime.strptime(value.strip(), fmt)
            dt = dt.replace(tzinfo=now.tzinfo)
            return dt.isoformat(timespec="seconds")
        except ValueError:
            continue

    # --- 5) Time-only formats (assume today) ---
    try:
        dt = _parse_time_only(value.strip(), now)
        return dt.isoformat(timespec="seconds")
    except ValueError:
        pass

    raise SystemExit(
        f"Could not parse time {value!r}. Try ISO like '2026-02-25T07:34:00-05:00' "
        f"or '2026-02-25 7:34am' or '7:34am' or 'yesterday 9am' or '3 days ago'."
    )


def _parse_time_only(time_str: str, base_dt: datetime) -> datetime:
    """
    Parse a time like '9am', '7:34am', '14:30' and apply it to base_dt's date.
    Returns timezone-aware datetime (base_dt tz).
    """
    s = time_str.strip().lower()

    t_formats = [
        "%I:%M%p",
        "%I:%M %p",
        "%I%p",
        "%H:%M",
    ]
    for fmt in t_formats:
        try:
            t = datetime.strptime(s, fmt)
            dt = base_dt.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
            return dt
        except ValueError:
            continue

    raise ValueError(f"Could not parse time-only value: {time_str!r}")