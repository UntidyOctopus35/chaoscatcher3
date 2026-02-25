from __future__ import annotations

import argparse
import os
import stat
from datetime import datetime

from .paths import resolve_data_path
from .safety import assert_safe_data_path
from .storage import load_json, save_json


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def cmd_med_add(args: argparse.Namespace) -> None:
    data = load_json(args.data_path)
    meds = data.setdefault("medications", [])

    ts = args.time if args.time else _now_iso()

    entry = {"ts": ts, "name": args.name, "dose": args.dose}
    if args.notes:
        entry["notes"] = args.notes

    meds.append(entry)
    save_json(args.data_path, data)

    print(f"💊 Logged: {entry['name']} {entry['dose']} @ {entry['ts']}")


def cmd_med_list(args: argparse.Namespace) -> None:
    data = load_json(args.data_path)
    meds = data.get("medications", [])

    if not meds:
        print("No medication entries yet.")
        return

    print("=== Medication Log (newest first) ===")
    for m in reversed(meds):
        line = f"{m.get('ts','')} — {m.get('name','')} {m.get('dose','')}".strip()
        if m.get("notes"):
            line += f" ({m['notes']})"
        print(line)


def cmd_init(args: argparse.Namespace) -> None:
    data = load_json(args.data_path)
    data.setdefault("daily_logs", {})
    data.setdefault("moods", [])
    data.setdefault("water", [])
    data.setdefault("medications", [])  # med-only build (no substances)
    save_json(args.data_path, data)

    # set 0600 best-effort
    try:
        os.chmod(args.data_path, 0o600)
    except OSError:
        pass

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
    p.add_argument(
        "--allow-repo-data-path",
        action="store_true",
        help="Override safety guard (not recommended)",
    )

    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="Initialize data store safely").set_defaults(func=cmd_init)
    sub.add_parser("summary", help="Show summary dashboard").set_defaults(func=cmd_summary)
    sub.add_parser("where", help="Show which data file is active and why").set_defaults(func=cmd_where)
    sub.add_parser("doctor", help="Run safety + health checks").set_defaults(func=cmd_doctor)

    # medication commands
    med = sub.add_parser("med", help="Medication logging")
    med_sub = med.add_subparsers(dest="med_cmd", required=True)

    med_add = med_sub.add_parser("add", help="Add medication entry")
    med_add.add_argument("--name", required=True)
    med_add.add_argument("--dose", required=True)
    med_add.add_argument("--time", default=None, help="ISO timestamp (default now)")
    med_add.add_argument("--notes", default=None)
    med_add.set_defaults(func=cmd_med_add)

    med_list = med_sub.add_parser("list", help="List medication entries")
    med_list.set_defaults(func=cmd_med_list)

    args = p.parse_args(argv)
    args.data_arg = args.data
    args.data_path = resolve_data_path(args.data, args.profile)

    assert_safe_data_path(args.data_path, args.allow_repo_data_path)

    args.func(args)