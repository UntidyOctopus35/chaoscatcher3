from __future__ import annotations

import argparse
import csv
import os
import stat
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any

from .paths import resolve_data_path
from .safety import assert_safe_data_path
from .storage import load_json, save_json
from .timeparse import parse_ts


# -------------------------
# Time helpers
# -------------------------

def _now_local() -> datetime:
    return datetime.now().astimezone()


def _now_iso() -> str:
    return _now_local().isoformat(timespec="seconds")


def _parse_ts(value: str | None) -> str:
    """
    Wrapper around timeparse.parse_ts:
    - None -> now
    - accepts ISO, human, and relative formats implemented in parse_ts
    Returns ISO string with local timezone.

    Defensive: parse_ts MUST ideally return a datetime, but if it returns a
    string (or something else), we try to coerce safely.
    """
    if not value:
        return _now_iso()

    dt_any = parse_ts(value)

    # Ideal path: datetime returned
    if isinstance(dt_any, datetime):
        dt = dt_any
    # If timeparse returns ISO string or similar, attempt to parse
    elif isinstance(dt_any, str):
        s = dt_any.strip()
        # Try ISO first
        try:
            dt = datetime.fromisoformat(s)
        except Exception:
            # Last resort: try parsing the ORIGINAL input as ISO
            # (keeps error messages more intuitive)
            try:
                dt = datetime.fromisoformat(str(value).strip())
            except Exception as e:
                raise SystemExit(f"Could not parse --time {value!r} (timeparse returned {dt_any!r})") from e
    else:
        raise SystemExit(f"Could not parse --time {value!r} (timeparse returned {type(dt_any).__name__})")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_now_local().tzinfo)

    return dt.astimezone().isoformat(timespec="seconds")


def _dt_from_entry_ts(ts: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_now_local().tzinfo)
        return dt.astimezone()
    except Exception:
        return None


def _window_cutoff(window: str) -> tuple[datetime | None, str]:
    now = _now_local()
    if window == "7":
        days = 7
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
        return cutoff, "last 7 days"
    if window == "30":
        days = 30
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
        return cutoff, "last 30 days"
    return None, "all time"


# -------------------------
# Formatting helpers
# -------------------------

def _fmt_time(dt: datetime) -> str:
    # Linux: %-I works; Windows: fallback
    try:
        return dt.strftime("%-I:%M %p")
    except ValueError:
        return dt.strftime("%I:%M %p").lstrip("0")


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts: list[str] = []
    for chunk in raw.replace(",", " ").split():
        c = chunk.strip()
        if c:
            parts.append(c)
    seen = set()
    out: list[str] = []
    for p in parts:
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _sparkline(values: list[float], vmin: float = 1.0, vmax: float = 10.0) -> str:
    if not values:
        return ""
    blocks = "▁▂▃▄▅▆▇█"
    span = max(1e-9, vmax - vmin)
    out = []
    for v in values:
        x = (v - vmin) / span
        idx = int(round(x * (len(blocks) - 1)))
        idx = max(0, min(len(blocks) - 1, idx))
        out.append(blocks[idx])
    return "".join(out)


def _parse_minutes(value: str | None, arg_name: str) -> int | None:
    """
    Accepts:
      - None -> None
      - "90" -> 90 minutes
      - "7:30" -> 7h 30m -> 450 minutes
      - "7h30m" / "7h" / "30m" -> parsed
    Returns minutes as int, or raises SystemExit on bad format.
    """
    if value is None:
        return None

    s = str(value).strip().lower()
    if not s:
        return None

    # 1) H:MM
    if ":" in s:
        parts = s.split(":")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            h = int(parts[0])
            m = int(parts[1])
            if m < 0 or m >= 60 or h < 0:
                raise SystemExit(f"{arg_name} must be minutes, or H:MM like 7:30")
            return h * 60 + m
        raise SystemExit(f"{arg_name} must be minutes, or H:MM like 7:30")

    # 2) plain minutes
    if s.isdigit():
        return int(s)

    # 3) "7h30m" variants
    total = 0
    num = ""
    saw_unit = False

    def flush(unit: str) -> None:
        nonlocal total, num, saw_unit
        if not num:
            raise SystemExit(f"{arg_name}: bad duration {value!r}")
        n = int(num)
        if unit == "h":
            total += n * 60
        elif unit == "m":
            total += n
        else:
            raise SystemExit(f"{arg_name}: bad duration {value!r}")
        num = ""
        saw_unit = True

    for ch in s:
        if ch.isdigit():
            num += ch
            continue
        if ch in ("h", "m"):
            flush(ch)
            continue
        if ch in (" ",):
            continue
        raise SystemExit(f"{arg_name} must be minutes, H:MM, or like 7h30m (got {value!r})")

    if num:
        # if they wrote "7" but not digits-only (handled above), treat as error
        if saw_unit:
            raise SystemExit(f"{arg_name}: trailing number without unit in {value!r}")
        raise SystemExit(f"{arg_name} must be minutes, H:MM, or like 7h30m (got {value!r})")

    return total if saw_unit else None


# -------------------------
# Print blocks
# -------------------------

def _print_med_block(entry: dict[str, Any]) -> None:
    dt = _dt_from_entry_ts(str(entry.get("ts", "")))
    if dt:
        d = dt.date().isoformat()
        t = _fmt_time(dt)
    else:
        d = "unknown-date"
        t = "unknown-time"

    name = str(entry.get("name", "")).strip()
    dose = str(entry.get("dose", "")).strip()
    notes = str(entry.get("notes", "")).strip()

    print("```")
    print("📒 Medication Log")
    print(f"- 📅 Date: {d}")
    print(f"- 🕒 Time: {t}")
    print(f"- 💊 Medication: {name}")
    print(f"- 🧪 Dose: {dose}")
    if notes:
        print(f"- 📝 Notes: {notes}")
    print("```")


def _print_mood_block(entry: dict[str, Any]) -> None:
    dt = _dt_from_entry_ts(str(entry.get("ts", "")))
    if dt:
        d = dt.date().isoformat()
        t = _fmt_time(dt)
    else:
        d = "unknown-date"
        t = "unknown-time"

    score = entry.get("score", None)
    notes = str(entry.get("notes", "")).strip()
    tags = entry.get("tags", [])

    sleep_total = entry.get("sleep_total_min")
    sleep_rem = entry.get("sleep_rem_min")
    sleep_deep = entry.get("sleep_deep_min")

    print("```")
    print("📒 Mood Log")
    print(f"- 📅 Date: {d}")
    print(f"- 🕒 Time: {t}")
    print(f"- 🙂 Mood (1–10): {score}")
    if tags:
        print(f"- 🏷️ Tags: {', '.join(tags)}")
    if sleep_total is not None or sleep_rem is not None or sleep_deep is not None:
        print("- 😴 Sleep (minutes): "
              f"total={sleep_total if sleep_total is not None else '—'}, "
              f"REM={sleep_rem if sleep_rem is not None else '—'}, "
              f"deep={sleep_deep if sleep_deep is not None else '—'}")
    if notes:
        print(f"- 📝 Notes: {notes}")
    print("```")


# -------------------------
# CSV helpers
# -------------------------

MOOD_CSV_FIELDS = [
    "ts",
    "date",
    "time",
    "timezone",
    "weekday",
    "score",
    "sleep_total_min",
    "sleep_rem_min",
    "sleep_deep_min",
    "tags",
    "notes",
]

MOOD_DAILY_CSV_FIELDS = [
    "date",
    "weekday",
    "avg_score",
    "min_score",
    "max_score",
    "entries",
    "avg_sleep_total_min",
    "avg_sleep_rem_min",
    "avg_sleep_deep_min",
    "tags_top",
]


def _write_csv(out_path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        if rows:
            w.writerows(rows)


# -------------------------
# MED commands
# -------------------------

def cmd_med_add(args: argparse.Namespace) -> None:
    data = load_json(args.data_path)
    meds = data.setdefault("medications", [])

    ts = _parse_ts(args.time)

    entry: dict[str, Any] = {"ts": ts, "name": args.name, "dose": args.dose}
    if args.notes:
        entry["notes"] = args.notes

    meds.append(entry)
    save_json(args.data_path, data)

    if args.format == "block":
        _print_med_block(entry)
    else:
        print(f"💊 Logged: {entry['name']} {entry['dose']} @ {entry['ts']}")


def cmd_med_list(args: argparse.Namespace) -> None:
    data = load_json(args.data_path)
    meds = data.get("medications", [])

    if not meds:
        print("No medication entries yet.")
        return

    meds_sorted = list(reversed(meds))  # newest first

    if args.format == "block":
        for m in meds_sorted[: args.limit]:
            _print_med_block(m)
        return

    print("=== Medication Log (newest first) ===")
    for m in meds_sorted[: args.limit]:
        line = f"{m.get('ts','')} — {m.get('name','')} {m.get('dose','')}".strip()
        if m.get("notes"):
            line += f" ({m['notes']})"
        print(line)


def cmd_med_today(args: argparse.Namespace) -> None:
    data = load_json(args.data_path)
    meds = data.get("medications", [])

    if not meds:
        print("No medication entries yet.")
        return

    today = _now_local().date()
    todays: list[dict[str, Any]] = []

    for m in meds:
        dt = _dt_from_entry_ts(str(m.get("ts", "")))
        if dt and dt.date() == today:
            todays.append(m)

    if not todays:
        print("No medication entries logged today.")
        return

    todays_sorted = list(reversed(todays))  # newest first

    if args.format == "block":
        for m in todays_sorted[: args.limit]:
            _print_med_block(m)
        return

    print(f"=== Medication Log (today: {today.isoformat()}) ===")
    for m in todays_sorted[: args.limit]:
        dt = _dt_from_entry_ts(str(m.get("ts", "")))
        t = _fmt_time(dt) if dt else ""
        print(f"{t} — {m.get('name','')} {m.get('dose','')}")


def cmd_med_stats(args: argparse.Namespace) -> None:
    data = load_json(args.data_path)
    meds = data.get("medications", [])

    if not meds:
        print("No medication entries yet.")
        return

    now = _now_local()
    cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=args.days - 1)

    counts: dict[str, int] = {}
    hour_counts: dict[int, int] = {}

    for m in meds:
        name = str(m.get("name", "Unknown")).strip() or "Unknown"
        dt = _dt_from_entry_ts(str(m.get("ts", "")))
        if not dt or dt < cutoff:
            continue

        counts[name] = counts.get(name, 0) + 1
        hour_counts[dt.hour] = hour_counts.get(dt.hour, 0) + 1

    if not counts:
        print(f"No medication entries found in last {args.days} days.")
        return

    print(f"=== Medication Stats (last {args.days} days, since {cutoff.date().isoformat()}) ===")
    print("\n[Counts by medication]")
    for name, c in sorted(counts.items(), key=lambda x: (-x[1], x[0].lower())):
        print(f"- {name}: {c}")

    print("\n[Most common hours]")
    top_hours = sorted(hour_counts.items(), key=lambda x: -x[1])[:5]
    for h, c in top_hours:
        # %-I is linux-only; use helper with safe fallback
        label = _fmt_time(datetime(2000, 1, 1, h, 0).astimezone())
        label = label.replace(":00", "")  # cosmetic: "3 PM"
        print(f"- {label}: {c}")


# -------------------------
# MOOD commands
# -------------------------

def cmd_mood_add(args: argparse.Namespace) -> None:
    if not (1 <= args.score <= 10):
        raise SystemExit("--score must be between 1 and 10")

    data = load_json(args.data_path)
    moods = data.setdefault("moods", [])

    ts = _parse_ts(args.time)
    entry: dict[str, Any] = {"ts": ts, "score": int(args.score)}

    if args.notes:
        entry["notes"] = args.notes

    tags = _parse_tags(args.tags)
    if tags:
        entry["tags"] = tags

    # Sleep fields (minutes)
    sleep_total = _parse_minutes(args.sleep_total, "--sleep-total")
    sleep_rem = _parse_minutes(args.sleep_rem, "--sleep-rem")
    sleep_deep = _parse_minutes(args.sleep_deep, "--sleep-deep")

    if sleep_total is not None:
        entry["sleep_total_min"] = sleep_total
    if sleep_rem is not None:
        entry["sleep_rem_min"] = sleep_rem
    if sleep_deep is not None:
        entry["sleep_deep_min"] = sleep_deep

    moods.append(entry)
    save_json(args.data_path, data)

    if args.format == "block":
        _print_mood_block(entry)
    else:
        print(f"🙂 Logged mood {entry['score']}/10 @ {entry['ts']}")


def cmd_mood_list(args: argparse.Namespace) -> None:
    data = load_json(args.data_path)
    moods = data.get("moods", [])

    if not moods:
        print("No mood entries yet.")
        return

    moods_sorted = list(reversed(moods))  # newest first

    if args.format == "block":
        for m in moods_sorted[: args.limit]:
            _print_mood_block(m)
        return

    print("=== Mood Log (newest first) ===")
    for m in moods_sorted[: args.limit]:
        ts = str(m.get("ts", ""))
        score = m.get("score", "")
        notes = m.get("notes")
        tags = m.get("tags", [])
        line = f"{ts} — {score}/10"
        if tags:
            line += f" [{', '.join(tags)}]"
        if notes:
            line += f" ({notes})"
        st = m.get("sleep_total_min")
        sr = m.get("sleep_rem_min")
        sd = m.get("sleep_deep_min")
        if st is not None or sr is not None or sd is not None:
            line += f" [sleep total={st if st is not None else '—'}m rem={sr if sr is not None else '—'}m deep={sd if sd is not None else '—'}m]"
        print(line)


def cmd_mood_today(args: argparse.Namespace) -> None:
    data = load_json(args.data_path)
    moods = data.get("moods", [])

    if not moods:
        print("No mood entries yet.")
        return

    today = _now_local().date()
    todays: list[dict[str, Any]] = []

    for m in moods:
        dt = _dt_from_entry_ts(str(m.get("ts", "")))
        if dt and dt.date() == today:
            todays.append(m)

    if not todays:
        print("No mood entries logged today.")
        return

    todays_sorted = list(reversed(todays))  # newest first

    if args.format == "block":
        for m in todays_sorted[: args.limit]:
            _print_mood_block(m)
        return

    print(f"=== Mood Log (today: {today.isoformat()}) ===")
    for m in todays_sorted[: args.limit]:
        dt = _dt_from_entry_ts(str(m.get("ts", "")))
        t = _fmt_time(dt) if dt else ""
        tags = m.get("tags", [])
        line = f"{t} — {m.get('score','')}/10"
        if tags:
            line += f" [{', '.join(tags)}]"
        st = m.get("sleep_total_min")
        sr = m.get("sleep_rem_min")
        sd = m.get("sleep_deep_min")
        if st is not None or sr is not None or sd is not None:
            line += f" [sleep total={st if st is not None else '—'}m rem={sr if sr is not None else '—'}m deep={sd if sd is not None else '—'}m]"
        print(line)


def cmd_mood_reset(args: argparse.Namespace) -> None:
    data = load_json(args.data_path)
    before = len(data.get("moods", []))

    if not args.yes:
        raise SystemExit("Refusing to reset without --yes (this deletes mood history).")

    data["moods"] = []
    save_json(args.data_path, data)
    print(f"🧹 Mood reset: deleted {before} entries.")


def _mood_key(entry: dict[str, Any]) -> tuple:
    ts = str(entry.get("ts", ""))
    score = int(entry.get("score", 0)) if isinstance(entry.get("score"), int) else entry.get("score")
    notes = str(entry.get("notes", "")).strip()
    tags = entry.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    tags_norm = tuple(sorted(str(t).strip().lower() for t in tags if str(t).strip()))
    sleep_total = entry.get("sleep_total_min")
    sleep_rem = entry.get("sleep_rem_min")
    sleep_deep = entry.get("sleep_deep_min")
    return (ts, score, notes, tags_norm, sleep_total, sleep_rem, sleep_deep)


def cmd_mood_dedupe(args: argparse.Namespace) -> None:
    data = load_json(args.data_path)
    moods = data.get("moods", [])

    if not moods:
        print("No mood entries yet.")
        return

    seen: set[tuple] = set()
    kept: list[dict[str, Any]] = []
    removed = 0

    for m in moods:
        k = _mood_key(m)
        if k in seen:
            removed += 1
            continue
        seen.add(k)
        kept.append(m)

    if removed == 0:
        print("✅ No duplicates found.")
        return

    if args.dry_run:
        print(f"🧪 Dedupe dry-run: would remove {removed} duplicates (keep {len(kept)}).")
        return

    data["moods"] = kept
    save_json(args.data_path, data)
    print(f"🧽 Dedupe complete: removed {removed} duplicates (kept {len(kept)}).")


def cmd_mood_stats(args: argparse.Namespace) -> None:
    data = load_json(args.data_path)
    moods = data.get("moods", [])

    if not moods:
        print("No mood entries yet.")
        return

    cutoff, label = _window_cutoff(args.window)

    recent: list[tuple[datetime, dict[str, Any]]] = []
    for m in moods:
        dt = _dt_from_entry_ts(str(m.get("ts", "")))
        if not dt:
            continue
        if cutoff and dt < cutoff:
            continue
        recent.append((dt, m))

    if not recent:
        print(f"No mood entries found for {label}.")
        return

    by_day: dict[str, list[int]] = {}
    tag_counts: dict[str, int] = {}

    for dt, m in recent:
        s = m.get("score")
        if isinstance(s, int) and 1 <= s <= 10:
            day = dt.date().isoformat()
            by_day.setdefault(day, []).append(s)

        for t in m.get("tags", []) or []:
            tag_counts[str(t)] = tag_counts.get(str(t), 0) + 1

    if not by_day:
        print(f"No valid mood scores found for {label}.")
        return

    days_sorted = sorted(by_day.keys())
    daily_avgs = [(d, sum(by_day[d]) / len(by_day[d])) for d in days_sorted]

    scores = [avg for _, avg in daily_avgs]
    avg = sum(scores) / len(scores)
    mn = min(scores)
    mx = max(scores)

    n = len(daily_avgs)
    xs = list(range(n))
    ys = scores

    if n == 1:
        slope = 0.0
        direction = "→ stable (not enough data)"
        net = 0.0
    else:
        x_mean = sum(xs) / n
        y_mean = sum(ys) / n
        num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
        den = sum((x - x_mean) ** 2 for x in xs)
        slope = (num / den) if den else 0.0

        eps = args.trend_epsilon
        if slope > eps:
            direction = "↑ increasing"
        elif slope < -eps:
            direction = "↓ decreasing"
        else:
            direction = "→ stable"

        net = ys[-1] - ys[0]

    dist: dict[int, int] = {i: 0 for i in range(1, 11)}
    raw_scores: list[int] = []
    for _, m in recent:
        s = m.get("score")
        if isinstance(s, int) and 1 <= s <= 10:
            raw_scores.append(s)
            dist[s] += 1

    best_day = max(daily_avgs, key=lambda x: x[1])
    worst_day = min(daily_avgs, key=lambda x: x[1])

    print(f"=== Mood Stats ({label}) ===")
    if cutoff:
        print(f"- since: {cutoff.date().isoformat()}")
    print(f"- entries: {len(raw_scores)}")
    print(f"- days with data: {len(daily_avgs)}")
    print(f"- average (daily): {avg:.2f}/10")
    print(f"- min/max (daily): {mn:.2f}/10 … {mx:.2f}/10")
    print(f"- best day (avg): {best_day[0]} = {best_day[1]:.2f}/10")
    print(f"- worst day (avg): {worst_day[0]} = {worst_day[1]:.2f}/10")

    print("\n[TREND]")
    print(f"- direction: {direction}")
    print(f"- slope: {slope:+.3f} mood points/day (epsilon={args.trend_epsilon})")
    print(f"- net change: {net:+.2f} (first day avg → last day avg)")
    print(f"- sparkline: {_sparkline(scores)}")

    print("\n[Daily averages]")
    for d, a in daily_avgs:
        print(f"- {d}: {a:.2f}/10 ({len(by_day[d])} entries)")

    print("\n[Score distribution (raw entries)]")
    for i in range(1, 11):
        bar = "▇" * min(dist[i], 30)
        print(f"{i:>2}: {dist[i]:>3} {bar}")

    if tag_counts:
        print("\n[Top tags]")
        top = sorted(tag_counts.items(), key=lambda x: -x[1])[:10]
        for t, c in top:
            print(f"- {t}: {c}")


def cmd_mood_export(args: argparse.Namespace) -> None:
    data = load_json(args.data_path)
    moods = data.get("moods", [])

    cutoff, label = _window_cutoff(args.window)

    rows: list[dict[str, Any]] = []

    for m in moods:
        ts = str(m.get("ts", "")).strip()
        dt = _dt_from_entry_ts(ts)
        if not dt:
            continue
        if cutoff and dt < cutoff:
            continue

        score = m.get("score")
        if not isinstance(score, int) or not (1 <= score <= 10):
            continue

        tags = m.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        tags_str = ", ".join(str(t).strip() for t in tags if str(t).strip())

        notes = str(m.get("notes", "")).strip()

        rows.append(
            {
                "ts": ts,
                "date": dt.date().isoformat(),
                "time": dt.strftime("%H:%M"),
                "timezone": dt.strftime("%z"),
                "weekday": dt.strftime("%a"),
                "score": score,
                "sleep_total_min": m.get("sleep_total_min", ""),
                "sleep_rem_min": m.get("sleep_rem_min", ""),
                "sleep_deep_min": m.get("sleep_deep_min", ""),
                "tags": tags_str,
                "notes": notes,
            }
        )

    out_path = Path(args.csv).expanduser().resolve()
    _write_csv(out_path, MOOD_CSV_FIELDS, rows)

    if rows:
        print(f"📄 Exported {len(rows)} mood rows ({label}) → {out_path}")
    else:
        print(f"📄 Exported header-only mood CSV (no rows for {label}) → {out_path}")


def cmd_mood_export_daily(args: argparse.Namespace) -> None:
    data = load_json(args.data_path)
    moods = data.get("moods", [])

    cutoff, label = _window_cutoff(args.window)

    by_day_scores: dict[str, list[int]] = {}
    by_day_tags: dict[str, list[str]] = {}
    by_day_sleep_total: dict[str, list[int]] = {}
    by_day_sleep_rem: dict[str, list[int]] = {}
    by_day_sleep_deep: dict[str, list[int]] = {}

    for m in moods:
        ts = str(m.get("ts", "")).strip()
        dt = _dt_from_entry_ts(ts)
        if not dt:
            continue
        if cutoff and dt < cutoff:
            continue

        s = m.get("score")
        if not isinstance(s, int) or not (1 <= s <= 10):
            continue

        day = dt.date().isoformat()
        by_day_scores.setdefault(day, []).append(s)

        tags = m.get("tags", [])
        if isinstance(tags, list):
            for t in tags:
                tt = str(t).strip()
                if tt:
                    by_day_tags.setdefault(day, []).append(tt)

        st = m.get("sleep_total_min")
        if isinstance(st, int) and st >= 0:
            by_day_sleep_total.setdefault(day, []).append(st)

        sr = m.get("sleep_rem_min")
        if isinstance(sr, int) and sr >= 0:
            by_day_sleep_rem.setdefault(day, []).append(sr)

        sd = m.get("sleep_deep_min")
        if isinstance(sd, int) and sd >= 0:
            by_day_sleep_deep.setdefault(day, []).append(sd)

    def _avg(xs: list[int]) -> str:
        if not xs:
            return ""
        return f"{(sum(xs) / len(xs)):.2f}"

    rows: list[dict[str, Any]] = []
    for day in sorted(by_day_scores.keys()):
        scores = by_day_scores[day]
        avg = sum(scores) / len(scores)
        mn = min(scores)
        mx = max(scores)
        entries = len(scores)

        tlist = by_day_tags.get(day, [])
        top_tags = ""
        if tlist:
            counts: dict[str, int] = {}
            for t in tlist:
                counts[t] = counts.get(t, 0) + 1
            top = sorted(counts.items(), key=lambda x: -x[1])[:5]
            top_tags = ", ".join(f"{t}({c})" for t, c in top)

        wd = ""
        try:
            wd = datetime.fromisoformat(day).strftime("%a")
        except Exception:
            wd = ""

        rows.append(
            {
                "date": day,
                "weekday": wd,
                "avg_score": f"{avg:.2f}",
                "min_score": mn,
                "max_score": mx,
                "entries": entries,
                "avg_sleep_total_min": _avg(by_day_sleep_total.get(day, [])),
                "avg_sleep_rem_min": _avg(by_day_sleep_rem.get(day, [])),
                "avg_sleep_deep_min": _avg(by_day_sleep_deep.get(day, [])),
                "tags_top": top_tags,
            }
        )

    out_path = Path(args.csv).expanduser().resolve()
    _write_csv(out_path, MOOD_DAILY_CSV_FIELDS, rows)

    if rows:
        print(f"📄 Exported {len(rows)} daily summary rows ({label}) → {out_path}")
    else:
        print(f"📄 Exported header-only daily summary CSV (no rows for {label}) → {out_path}")


# -------------------------
# Core commands
# -------------------------

def cmd_init(args: argparse.Namespace) -> None:
    data = load_json(args.data_path)
    data.setdefault("daily_logs", {})
    data.setdefault("water", [])
    data.setdefault("medications", [])
    data.setdefault("moods", [])
    save_json(args.data_path, data)
    print(f"✅ Initialized data file: {args.data_path}")


def cmd_where(args: argparse.Namespace) -> None:
    env = os.environ.get("CHAOSCATCHER_DATA")
    if args.data_arg:
        reason = "because you passed --data"
    elif env:
        reason = "because CHAOSCATCHER_DATA is set"
    elif args.profile:
        reason = f"because you used --profile {args.profile!r}"
    else:
        reason = "default XDG config location"

    print(args.data_path)
    print(f"↳ using {reason}")


def cmd_doctor(args: argparse.Namespace) -> None:
    print("=== ChaosCatcher Doctor ===")

    assert_safe_data_path(args.data_path, args.allow_repo_data_path)
    print("✅ Data path safety guard: OK")

    data = load_json(args.data_path)
    if isinstance(data, dict):
        print("✅ JSON readable: OK")

    try:
        mode = args.data_path.stat().st_mode
        perms = stat.S_IMODE(mode)
        print(f"🔐 File permissions: {oct(perms)} (target 0o600)")
    except FileNotFoundError:
        print("⚠️ Data file missing (run `cc init`)")

    print("=== Done ===")


def cmd_summary(args: argparse.Namespace) -> None:
    data = load_json(args.data_path)

    print("====================")
    print("ChaosCatcher Summary")
    print("====================\n")

    print("[DATA PATH]")
    print(args.data_path, "\n")

    print("[MOOD – last 7 days]")
    moods = data.get("moods", [])
    if moods:
        by_day: dict[str, list[int]] = {}
        for m in moods:
            dt = _dt_from_entry_ts(str(m.get("ts", "")))
            if not dt:
                continue
            day = dt.date().isoformat()
            s = m.get("score")
            if isinstance(s, int) and 1 <= s <= 10:
                by_day.setdefault(day, []).append(s)

        days = sorted(by_day.keys())[-7:]
        if not days:
            print("No mood entries yet.")
        else:
            for d in days:
                vals = by_day[d]
                avg = sum(vals) / len(vals)
                print(f"- {d}: {avg:.2f}/10 ({len(vals)} entries)")
    else:
        print("No mood entries yet.")

    print("\n[MEDICATION – today]")
    meds = data.get("medications", [])
    today = _now_local().date().isoformat()
    todays = []
    for m in meds:
        dt = _dt_from_entry_ts(str(m.get("ts", "")))
        if dt and dt.date().isoformat() == today:
            todays.append(m)
    if todays:
        for m in reversed(todays):
            dt = _dt_from_entry_ts(str(m.get("ts", "")))
            t = _fmt_time(dt) if dt else ""
            print(f"- {t}: {m.get('name','')} {m.get('dose','')}")
    else:
        print("No meds logged today.")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="cc", description="ChaosCatcher self-care suite")
    p.add_argument("--data", default=None, help="Path to data JSON (overrides env/default)")
    p.add_argument("--profile", default=None, help="Profile name (e.g. dev/test)")
    p.add_argument("--allow-repo-data-path", action="store_true", help="Override safety guard (not recommended)")

    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="Initialize data store safely").set_defaults(func=cmd_init)
    sub.add_parser("summary", help="Show summary dashboard").set_defaults(func=cmd_summary)
    sub.add_parser("where", help="Show which data file is active and why").set_defaults(func=cmd_where)
    sub.add_parser("doctor", help="Run safety + health checks").set_defaults(func=cmd_doctor)

    # ---- med ----
    med = sub.add_parser("med", help="Medication logging")
    med_sub = med.add_subparsers(dest="med_cmd", required=True)

    med_add = med_sub.add_parser("add", help="Add medication entry")
    med_add.add_argument("--name", required=True)
    med_add.add_argument("--dose", required=True)
    med_add.add_argument("--time", default=None, help="ISO, human, or relative (e.g. today 9am)")
    med_add.add_argument("--notes", default=None)
    med_add.add_argument("--format", choices=["line", "block"], default="line")
    med_add.set_defaults(func=cmd_med_add)

    med_list = med_sub.add_parser("list", help="List medication entries")
    med_list.add_argument("--limit", type=int, default=50)
    med_list.add_argument("--format", choices=["line", "block"], default="line")
    med_list.set_defaults(func=cmd_med_list)

    med_today = med_sub.add_parser("today", help="List today's medication entries")
    med_today.add_argument("--limit", type=int, default=50)
    med_today.add_argument("--format", choices=["line", "block"], default="line")
    med_today.set_defaults(func=cmd_med_today)

    med_stats = med_sub.add_parser("stats", help="Basic stats for recent medication logs")
    med_stats.add_argument("--days", type=int, default=14, help="Lookback window (days)")
    med_stats.set_defaults(func=cmd_med_stats)

    # ---- mood ----
    mood = sub.add_parser("mood", help="Mood tracking + analysis")
    mood_sub = mood.add_subparsers(dest="mood_cmd", required=True)

    mood_add = mood_sub.add_parser("add", help="Add mood entry (1–10)")
    mood_add.add_argument("--score", type=int, required=True, help="Mood score 1–10")
    mood_add.add_argument("--time", default=None, help="ISO, human, or relative (e.g. today 9am, 3 days ago)")
    mood_add.add_argument("--notes", default=None)
    mood_add.add_argument("--tags", default=None, help="Comma or space-separated tags (e.g. baseline,school)")
    mood_add.add_argument("--sleep-total", dest="sleep_total", default=None,
                          help="Total sleep (minutes, H:MM like 7:30, or 7h30m)")
    mood_add.add_argument("--sleep-rem", dest="sleep_rem", default=None,
                          help="REM sleep (minutes, H:MM, or 1h15m)")
    mood_add.add_argument("--sleep-deep", dest="sleep_deep", default=None,
                          help="Deep sleep (minutes, H:MM, or 0h45m)")
    mood_add.add_argument("--format", choices=["line", "block"], default="line")
    mood_add.set_defaults(func=cmd_mood_add)

    mood_list = mood_sub.add_parser("list", help="List mood entries")
    mood_list.add_argument("--limit", type=int, default=50)
    mood_list.add_argument("--format", choices=["line", "block"], default="line")
    mood_list.set_defaults(func=cmd_mood_list)

    mood_today = mood_sub.add_parser("today", help="List today's mood entries")
    mood_today.add_argument("--limit", type=int, default=50)
    mood_today.add_argument("--format", choices=["line", "block"], default="line")
    mood_today.set_defaults(func=cmd_mood_today)

    mood_stats = mood_sub.add_parser("stats", help="Mood stats + trend over time")
    mood_stats.add_argument("--window", choices=["7", "30", "all"], default="7",
                            help="Time window for analysis: 7, 30, or all")
    mood_stats.add_argument("--trend-epsilon", type=float, default=0.05,
                            help="Trend sensitivity in mood points/day (default 0.05)")
    mood_stats.set_defaults(func=cmd_mood_stats)

    mood_export = mood_sub.add_parser("export", help="Export mood entries to a clinician-friendly CSV")
    mood_export.add_argument("--csv", required=True, help="Output CSV path (e.g. ~/moods.csv)")
    mood_export.add_argument("--window", choices=["7", "30", "all"], default="30",
                             help="Time window for export: 7, 30, or all (default 30)")
    mood_export.set_defaults(func=cmd_mood_export)

    mood_export_daily = mood_sub.add_parser("export-daily", help="Export daily mood summary CSV (avg/min/max)")
    mood_export_daily.add_argument("--csv", required=True, help="Output CSV path (e.g. ~/moods_daily.csv)")
    mood_export_daily.add_argument("--window", choices=["7", "30", "all"], default="30",
                                   help="Time window for export: 7, 30, or all (default 30)")
    mood_export_daily.set_defaults(func=cmd_mood_export_daily)

    mood_reset = mood_sub.add_parser("reset", help="Delete ALL mood entries (requires --yes)")
    mood_reset.add_argument("--yes", action="store_true", help="Confirm destructive reset")
    mood_reset.set_defaults(func=cmd_mood_reset)

    mood_dedupe = mood_sub.add_parser("dedupe", help="Remove exact duplicate mood entries")
    mood_dedupe.add_argument("--dry-run", action="store_true", help="Show what would happen without writing")
    mood_dedupe.set_defaults(func=cmd_mood_dedupe)

    args = p.parse_args(argv)
    args.data_arg = args.data
    args.data_path = resolve_data_path(args.data, args.profile)

    assert_safe_data_path(args.data_path, args.allow_repo_data_path)

    args.func(args)