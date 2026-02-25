from __future__ import annotations

import argparse
import os
import stat
from datetime import datetime
from typing import Any

from .paths import resolve_data_path
from .safety import assert_safe_data_path
from .storage import load_json, save_json


# -------------------------
# Time helpers
# -------------------------

def _now_local() -> datetime:
    return datetime.now().astimezone()


def _now_iso() -> str:
    return _now_local().isoformat(timespec="seconds")


def _parse_ts(value: str | None) -> str:
    """
    Accepts:
      - None -> now
      - ISO 8601 (with or without tz; naive assumed local)
      - "7:34am", "7:34 am", "19:34", "7am"
      - "2026-02-25 7:34am", "2026-02-25 19:34"
    Returns ISO string with local timezone.
    """
    if not value:
        return _now_iso()

    s = value.strip()

    # 1) Try ISO first
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_now_local().tzinfo)
        return dt.astimezone().isoformat(timespec="seconds")
    except ValueError:
        pass

    # 2) Try date + time formats
    dt_formats = [
        "%Y-%m-%d %I:%M%p",
        "%Y-%m-%d %I:%M %p",
        "%Y-%m-%d %I%p",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %I:%M%p",
        "%Y/%m/%d %H:%M",
    ]
    for fmt in dt_formats:
        try:
            dt = datetime.strptime(s, fmt)
            dt = dt.replace(tzinfo=_now_local().tzinfo)
            return dt.isoformat(timespec="seconds")
        except ValueError:
            continue

    # 3) Try time-only formats (assume today)
    t_formats = [
        "%I:%M%p",
        "%I:%M %p",
        "%I%p",
        "%H:%M",
    ]
    for fmt in t_formats:
        try:
            t = datetime.strptime(s, fmt)
            now = _now_local()
            dt = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
            return dt.isoformat(timespec="seconds")
        except ValueError:
            continue

    raise SystemExit(
        f"Could not parse time {value!r}. Try ISO like '2026-02-25T07:34:00-05:00' "
        f"or human time like '7:34am' or '2026-02-25 7:34am'."
    )


def _dt_from_entry_ts(ts: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_now_local().tzinfo)
        return dt.astimezone()
    except Exception:
        return None


# -------------------------
# Formatting helpers
# -------------------------

def _fmt_time(dt: datetime) -> str:
    # %-I is not supported on Windows; but you're on Linux so it's fine.
    try:
        return dt.strftime("%-I:%M %p")
    except ValueError:
        return dt.strftime("%I:%M %p").lstrip("0")


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


# -------------------------
# Commands
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

    from datetime import timedelta

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
        label = datetime(2000, 1, 1, h, 0).strftime("%-I %p")
        print(f"- {label}: {c}")


def cmd_init(args: argparse.Namespace) -> None:
    data = load_json(args.data_path)
    data.setdefault("daily_logs", {})
    data.setdefault("moods", [])
    data.setdefault("water", [])
    data.setdefault("medications", [])  # med-only build
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

    print("[DAILY LOGS – last 7 days]")
    logs = data.get("daily_logs", {})
    if not logs:
        print("No dated entries yet.")
        return

    keys = sorted(logs.keys())[-7:]
    for k in keys:
        print(f"- {k}: {logs[k]}")


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

    # med commands
    med = sub.add_parser("med", help="Medication logging")
    med_sub = med.add_subparsers(dest="med_cmd", required=True)

    med_add = med_sub.add_parser("add", help="Add medication entry")
    med_add.add_argument("--name", required=True)
    med_add.add_argument("--dose", required=True)
    med_add.add_argument("--time", default=None, help="ISO or human time (e.g. 7:34am)")
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

    args = p.parse_args(argv)
    args.data_arg = args.data
    args.data_path = resolve_data_path(args.data, args.profile)

    assert_safe_data_path(args.data_path, args.allow_repo_data_path)

    args.func(args)