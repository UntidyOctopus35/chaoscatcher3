from __future__ import annotations

import csv
import json
import os
import sys
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

from ._util import _dt_from_entry_ts, _fmt_time, _now_local
from .paths import resolve_data_path
from .safety import assert_safe_data_path
from .storage import load_json, save_json
from .timeparse import parse_ts


def _parse_ts(value: str | None) -> str:
    """
    Accepts:
      - blank -> now
      - "today" / "now" -> now
      - "today 7:34am" -> today at 7:34am
      - ISO datetime strings
      - anything parse_ts() understands
    Returns ISO string with timezone, seconds precision.
    """
    if value is None:
        return _now_local().isoformat(timespec="seconds")

    raw = str(value).strip()
    if not raw:
        return _now_local().isoformat(timespec="seconds")

    s = raw.lower().strip()

    if s in ("today", "now"):
        return _now_local().isoformat(timespec="seconds")

    if s.startswith("today "):
        rest = raw[6:].strip()
        today = _now_local().date().isoformat()
        return _parse_ts(f"{today} {rest}")

    try:
        return parse_ts(raw)
    except BaseException as e:
        raise ValueError(
            "Could not parse time. Try: '7:34am', 'today 7:34am', 'yesterday 9am', "
            "or ISO like '2026-02-25T07:34:00-05:00'."
        ) from e


def _default_daily_med_list() -> list[dict[str, str]]:
    return [
        # {"name": "Vyvanse", "dose": "50 mg"},
        # {"name": "Gabapentin", "dose": "300 mg"},
    ]


def _linear_regression_slope(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    den = sum((x - x_mean) ** 2 for x in xs)
    return (num / den) if den else 0.0


def _parse_minutes(value: str | None) -> int | None:
    if value is None:
        return None
    s = str(value).strip().lower()
    if not s:
        return None

    if ":" in s:
        parts = s.split(":")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            h = int(parts[0])
            m = int(parts[1])
            if m < 0 or m >= 60 or h < 0:
                raise ValueError("Bad H:MM format")
            return h * 60 + m
        raise ValueError("Bad H:MM format")

    if s.isdigit():
        return int(s)

    total = 0
    num = ""
    saw_unit = False

    def flush(unit: str) -> None:
        nonlocal total, num, saw_unit
        if not num:
            raise ValueError("Bad duration")
        n = int(num)
        if unit == "h":
            total += n * 60
        elif unit == "m":
            total += n
        else:
            raise ValueError("Bad duration")
        num = ""
        saw_unit = True

    for ch in s:
        if ch.isdigit():
            num += ch
        elif ch in ("h", "m"):
            flush(ch)
        elif ch == " ":
            continue
        else:
            raise ValueError("Bad duration")

    if num:
        if saw_unit:
            raise ValueError("Trailing number without unit")
        raise ValueError("Bad duration")

    return total if saw_unit else None


def _trend_label_from_slope(slope: float, stable_band: float = 0.02) -> str:
    """
    slope = change in avg mood per day.
    stable_band = threshold below which we call it 'Stable'.
    """
    if slope > stable_band:
        return "Increasing"
    if slope < -stable_band:
        return "Decreasing"
    return "Stable"


def _pearson_corr(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denx = sum((x - mx) ** 2 for x in xs)
    deny = sum((y - my) ** 2 for y in ys)
    if denx <= 0 or deny <= 0:
        return None
    return num / ((denx**0.5) * (deny**0.5))


# -------------------------
# Vyvanse phase shading
# -------------------------

VY_PHASE_COLORS = {
    "Not yet": "#6b7280",  # gray
    "Loading": "#94a3b8",  # slate
    "Onset": "#60a5fa",  # blue
    "Peak": "#22c55e",  # green
    "Plateau": "#14b8a6",  # teal
    "Taper": "#f59e0b",  # amber
    "Tail": "#a78bfa",  # violet
}


def _vy_color_for_phase(phase: str) -> str:
    return VY_PHASE_COLORS.get(phase, "#94a3b8")


# -------------------------
# Mood graph color zones
# -------------------------

MOOD_ZONE_RED = "#ffe5e5"
MOOD_ZONE_YELLOW = "#fff4d6"
MOOD_ZONE_GREEN = "#e7f7e7"

MOOD_LINE_RED = "#b00020"
MOOD_LINE_YELLOW = "#b26a00"
MOOD_LINE_GREEN = "#0b6b2a"


# -------------------------
# Data access
# -------------------------


class Store:
    def __init__(self, data_path: Path):
        self.data_path = data_path

    def load(self) -> dict[str, Any]:
        try:
            d = load_json(self.data_path)
        except Exception:
            d = {}
        if not isinstance(d, dict):
            d = {}

        d.setdefault("medications", [])
        d.setdefault("moods", [])
        d.setdefault("daily_logs", {})
        d.setdefault("water", [])
        d.setdefault("daily_med_list", _default_daily_med_list())

        # Water goals:
        # - global default goal (oz)
        # - per-day overrides stored in daily_logs[YYYY-MM-DD]["water_goal_oz"]
        d.setdefault("water_goal_oz", 80)

        if not isinstance(d.get("daily_logs"), dict):
            d["daily_logs"] = {}

        d.setdefault("focus_sessions", [])

        return d

    def save(self, data: dict[str, Any]) -> None:
        save_json(self.data_path, data)


class ChaosCatcherApp(tk.Tk):
    def __init__(self, store: Store):
        super().__init__()
        self.title("ChaosCatcher")
        self.geometry("900x600")
        self.store = store

        self._graph_redraw_job: str | None = None
        self._graph_tooltip: tk.Toplevel | None = None

        self._focus_running: bool = False
        self._focus_job: str | None = None
        self._focus_phase: str = "work"  # "work" | "short_break" | "long_break"
        self._focus_session_count: int = 0  # completed work sessions this cycle
        self._focus_seconds_left: int = 25 * 60
        self._focus_session_start_ts: str | None = None  # ts when current work session started

        self._build_header()
        self._build_tabs()
        self._refresh_all_lists()

        self._refresh_vyvanse_chip()
        self.after(60_000, self._tick_vyvanse_chip)  # update every minute
        self.after(120, self._draw_mood_graph)

    # -------- Crash guard --------

    def report_callback_exception(self, exc, val, tb):  # type: ignore[override]
        import traceback

        traceback.print_exception(exc, val, tb)
        try:
            messagebox.showerror("Crash prevented", f"{exc.__name__}: {val}")
        except Exception:
            pass

    def _safe_cmd(self, fn):
        def wrapped(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except BaseException as e:
                import traceback

                traceback.print_exc()
                try:
                    messagebox.showerror("Crash prevented", f"{type(e).__name__}: {e}")
                except Exception:
                    pass
                return None

        return wrapped

    def _normalize_name(self, s: object) -> str:
        return str(s or "").strip().lower()

    # -------------------------
    # Header
    # -------------------------

    def _build_header(self) -> None:
        # Phase bar (simple + reliable shading indicator)
        self.vy_phase_bar = tk.Frame(self, height=6, bg="#94a3b8")
        self.vy_phase_bar.pack(fill="x", side="top")

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="x")

        left = ttk.Frame(frm)
        left.pack(side="left", fill="x", expand=True)

        right = ttk.Frame(frm)
        right.pack(side="right")

        ttk.Label(left, text="ChaosCatcher", font=("TkDefaultFont", 16, "bold")).pack(side="left")

        self.path_var = tk.StringVar(value=str(self.store.data_path))
        ttk.Label(left, textvariable=self.path_var, foreground="#666").pack(side="left", padx=12)

        btns = ttk.Frame(right)
        btns.pack(side="left")

        ttk.Button(btns, text="Refresh", command=self._safe_cmd(self._refresh_all_lists)).pack(side="left", padx=4)
        ttk.Button(
            btns,
            text="Open Data Folder",
            command=self._safe_cmd(self._open_data_folder),
        ).pack(side="left", padx=4)
        ttk.Button(btns, text="Log Vyvanse", command=self._safe_cmd(self._vyvanse_quick_log)).pack(side="left", padx=4)

        # Vyvanse arc chip (click for details)
        self.vy_arc_label = ttk.Label(right, text="Vyvanse: —", foreground="#444", cursor="hand2")
        self.vy_arc_label.pack(side="left", padx=(12, 0))
        self.vy_arc_label.bind("<Button-1>", lambda _e: self._show_vyvanse_popup())

    def _open_data_folder(self) -> None:
        p = self.store.data_path
        folder = p.parent
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(folder))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess

                subprocess.run(["open", str(folder)], check=False)
            else:
                import subprocess

                subprocess.run(["xdg-open", str(folder)], check=False)
            return
        except Exception:
            pass
        messagebox.showinfo("Data location", f"Data file:\n{p}\n\nFolder:\n{folder}")

    # -------------------------
    # Tabs
    # -------------------------

    def _build_tabs(self) -> None:
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_med = ttk.Frame(self.nb, padding=10)
        self.tab_mood = ttk.Frame(self.nb, padding=10)
        self.tab_water = ttk.Frame(self.nb, padding=10)
        self.tab_stats = ttk.Frame(self.nb, padding=10)
        self.tab_export = ttk.Frame(self.nb, padding=10)
        self.tab_focus = ttk.Frame(self.nb, padding=10)

        self.nb.add(self.tab_med, text="Medication")
        self.nb.add(self.tab_mood, text="Mood")
        self.nb.add(self.tab_water, text="Water")
        self.nb.add(self.tab_stats, text="Stats")
        self.nb.add(self.tab_export, text="Export")
        self.nb.add(self.tab_focus, text="Focus")

        self._build_med_tab()
        self._build_mood_tab()
        self._build_water_tab()
        self._build_stats_tab()
        self._build_export_tab()
        self._build_focus_tab()

    # -------- Helpers --------

    def _labeled_entry(self, parent: ttk.Frame, label: str, var: tk.StringVar) -> None:
        ttk.Label(parent, text=label).pack(anchor="w")
        ttk.Entry(parent, textvariable=var, width=30).pack(anchor="w", pady=(0, 8))

    def _today_key(self) -> str:
        return _now_local().date().isoformat()

    def _refresh_all_lists(self) -> None:
        self._refresh_med_list()
        self._refresh_mood_list()
        self._refresh_water_list()
        self._draw_mood_graph()
        self._refresh_vyvanse_chip()
        self._refresh_water_today_chip()

    def _write_stats(self, text: str) -> None:
        if not hasattr(self, "stats_out"):
            return
        self.stats_out.delete("1.0", tk.END)
        self.stats_out.insert(tk.END, text)

    def _analysis_write(self, text: str) -> None:
        if not hasattr(self, "analysis_out"):
            return
        self.analysis_out.delete("1.0", tk.END)
        self.analysis_out.insert(tk.END, text)

    # -------------------------
    # Medication tab
    # -------------------------

    def _build_med_tab(self) -> None:
        left = ttk.Frame(self.tab_med)
        right = ttk.Frame(self.tab_med)
        left.pack(side="left", fill="y", padx=(0, 10))
        right.pack(side="right", fill="both", expand=True)

        ttk.Label(left, text="Add medication", font=("TkDefaultFont", 12, "bold")).pack(anchor="w", pady=(0, 8))

        self.med_name = tk.StringVar()
        self.med_dose = tk.StringVar()
        self.med_time = tk.StringVar(value="")
        self.med_notes = tk.StringVar()

        self._labeled_entry(left, "Name", self.med_name)
        self._labeled_entry(left, "Dose", self.med_dose)
        self._labeled_entry(left, "Time (e.g. today 7:34am)", self.med_time)
        self._labeled_entry(left, "Notes (optional)", self.med_notes)

        ttk.Button(left, text="Add Medication", command=self._safe_cmd(self._med_add)).pack(fill="x", pady=(8, 0))
        ttk.Button(left, text="Took all daily meds", command=self._safe_cmd(self._med_take_all)).pack(
            fill="x", pady=(6, 0)
        )

        ttk.Separator(right).pack(fill="x", pady=(0, 8))
        ttk.Label(
            right,
            text="Medication log (newest first)",
            font=("TkDefaultFont", 12, "bold"),
        ).pack(anchor="w")

        self.med_list = tk.Listbox(right, height=20)
        self.med_list.pack(fill="both", expand=True, pady=8)

        ttk.Button(
            right,
            text="Delete selected (careful)",
            command=self._safe_cmd(self._med_delete_selected),
        ).pack(anchor="e")

    def _med_add(self) -> None:
        name = self.med_name.get().strip()
        dose = self.med_dose.get().strip()
        t = self.med_time.get().strip()
        notes = self.med_notes.get().strip()

        if not name:
            messagebox.showerror("Missing name", "Please enter a medication name.")
            return
        if not dose:
            messagebox.showerror("Missing dose", "Please enter a dose (e.g. 50 mg).")
            return

        try:
            ts = _parse_ts(t)
        except Exception as e:
            messagebox.showerror("Bad time", str(e))
            return

        entry: dict[str, Any] = {"ts": ts, "name": name, "dose": dose}
        if notes:
            entry["notes"] = notes

        data = self.store.load()
        data.setdefault("medications", []).append(entry)
        self.store.save(data)

        self.med_name.set("")
        self.med_dose.set("")
        self.med_time.set("")
        self.med_notes.set("")

        self._refresh_med_list()
        self._refresh_vyvanse_chip()

    def _med_take_all(self) -> None:
        data = self.store.load()
        template = data.get("daily_med_list", [])

        if not isinstance(template, list) or not template:
            messagebox.showinfo(
                "Daily meds list empty",
                "No daily meds are configured yet.\n\n"
                "Edit 'daily_med_list' in your data JSON (or we can add a GUI editor).",
            )
            return

        ts = _now_local().isoformat(timespec="seconds")
        meds = data.setdefault("medications", [])

        added = 0
        for item in template:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            dose = str(item.get("dose", "")).strip()
            notes = str(item.get("notes", "")).strip()

            if not name or not dose:
                continue

            entry: dict[str, Any] = {"ts": ts, "name": name, "dose": dose}
            if notes:
                entry["notes"] = notes

            meds.append(entry)
            added += 1

        self.store.save(data)
        self._refresh_med_list()
        self._refresh_vyvanse_chip()
        messagebox.showinfo("Logged", f"Added {added} meds at {_fmt_time(_now_local())}.")

    def _med_delete_selected(self) -> None:
        sel = self.med_list.curselection()
        if not sel:
            return
        if not messagebox.askyesno("Confirm delete", "Delete selected medication entry? This cannot be undone."):
            return

        idx = sel[0]
        data = self.store.load()
        meds = data.get("medications", [])
        meds_sorted = sorted(meds, key=lambda m: str(m.get("ts", "")), reverse=True)
        if idx < 0 or idx >= len(meds_sorted):
            return
        target = meds_sorted[idx]

        for i, m in enumerate(meds):
            if m == target:
                meds.pop(i)
                break

        data["medications"] = meds
        self.store.save(data)
        self._refresh_med_list()
        self._refresh_vyvanse_chip()

    def _refresh_med_list(self) -> None:
        self.med_list.delete(0, tk.END)
        data = self.store.load()
        meds = sorted(data.get("medications", []), key=lambda m: str(m.get("ts", "")), reverse=True)

        for m in meds:
            dt = _dt_from_entry_ts(str(m.get("ts", "")))
            when = f"{dt.date().isoformat()} {_fmt_time(dt)}" if dt else str(m.get("ts", ""))
            notes = m.get("notes", "")
            line = f"{when} — {m.get('name', '')} {m.get('dose', '')}"
            if notes:
                line += f"  |  {notes}"
            self.med_list.insert(tk.END, line)

    # -------------------------
    # Vyvanse arc helpers
    # -------------------------

    def _find_latest_vyvanse_entry(self):
        data = self.store.load()
        meds = data.get("medications", [])
        best_entry = None
        best_dt = None

        for m in meds:
            name = str(m.get("name", "")).strip().lower()
            if ("vyvanse" not in name) and ("vyv" not in name):
                continue
            dt = _dt_from_entry_ts(str(m.get("ts", "")))
            if not dt:
                continue
            if best_dt is None or dt > best_dt:
                best_dt = dt
                best_entry = m

        return best_entry, best_dt

    def _vyvanse_last_dose_guess(self) -> str:
        entry, _dt = self._find_latest_vyvanse_entry()
        if entry:
            d = str(entry.get("dose", "")).strip()
            if d:
                return d
        return "50 mg"

    def _vyvanse_arc_phase(self, t_minutes: float) -> str:
        if t_minutes < 0:
            return "Not yet"
        if t_minutes < 30:
            return "Loading"
        if t_minutes < 90:
            return "Onset"
        if t_minutes < 300:
            return "Peak"
        if t_minutes < 480:
            return "Plateau"
        if t_minutes < 660:
            return "Taper"
        return "Tail"

    def _fmt_hm(self, minutes: int) -> str:
        h = minutes // 60
        m = minutes % 60
        if h <= 0:
            return f"{m}m"
        return f"{h}h {m:02d}m"

    def _build_vyvanse_chip_text(self, dose_dt: datetime):
        now = _now_local()
        delta = now - dose_dt
        t_min = delta.total_seconds() / 60.0
        phase = self._vyvanse_arc_phase(t_min)
        t_pretty = self._fmt_hm(max(0, int(round(t_min))))
        chip = f"Vyvanse: {phase} (T+{t_pretty})"
        return chip, phase, t_min

    def _vyvanse_details_text(self, entry, dose_dt: datetime, phase: str, t_min: float) -> str:
        try:
            taken_str = dose_dt.strftime("%I:%M %p").lstrip("0")
        except Exception:
            taken_str = str(dose_dt)

        dose = (entry or {}).get("dose") or (entry or {}).get("amount") or ""
        notes = (entry or {}).get("notes") or ""

        windows = [
            ("Loading", (0, 30)),
            ("Onset", (30, 90)),
            ("Peak", (90, 300)),
            ("Plateau", (300, 480)),
            ("Taper", (480, 660)),
            ("Tail", (660, None)),
        ]

        lines: list[str] = []
        lines.append(f"Taken: {taken_str}")
        if dose:
            lines.append(f"Dose: {dose}")
        lines.append(f"Now: {_now_local().strftime('%I:%M %p').lstrip('0')}")
        lines.append(f"Current: {phase} (T+{self._fmt_hm(max(0, int(round(t_min))))})")
        lines.append("")
        lines.append("Arc model:")
        for label, (a, b) in windows:
            if b is None:
                lines.append(f"• {label}: {self._fmt_hm(a)}+")
            else:
                lines.append(f"• {label}: {self._fmt_hm(a)}–{self._fmt_hm(b)}")

        if notes:
            lines.append("")
            lines.append("Notes:")
            lines.append(str(notes))

        return "\n".join(lines)

    def _show_vyvanse_popup(self) -> None:
        entry, dt = self._find_latest_vyvanse_entry()
        if not entry or not dt:
            messagebox.showinfo("Vyvanse Arc", "No Vyvanse dose found in your med log.")
            return

        _chip, phase, t_min = self._build_vyvanse_chip_text(dt)
        details = self._vyvanse_details_text(entry, dt, phase, t_min)
        messagebox.showinfo("Vyvanse Arc", details)

    def _refresh_vyvanse_chip(self) -> None:
        if not hasattr(self, "vy_arc_label"):
            return

        entry, dt = self._find_latest_vyvanse_entry()
        if not entry or not dt:
            self.vy_arc_label.configure(text="Vyvanse: —")
            if hasattr(self, "vy_phase_bar"):
                self.vy_phase_bar.configure(bg="#94a3b8")
            return

        chip, phase, _t_min = self._build_vyvanse_chip_text(dt)
        self.vy_arc_label.configure(text=chip)

        if hasattr(self, "vy_phase_bar"):
            self.vy_phase_bar.configure(bg=_vy_color_for_phase(phase))

    def _tick_vyvanse_chip(self) -> None:
        self._refresh_vyvanse_chip()
        self.after(60_000, self._tick_vyvanse_chip)

    def _vyvanse_quick_log(self) -> None:
        default_dose = self._vyvanse_last_dose_guess()

        dose = simpledialog.askstring(
            "Log Vyvanse",
            "Dose (e.g. 50 mg):",
            initialvalue=default_dose,
            parent=self,
        )
        if dose is None:
            return
        dose = dose.strip()
        if not dose:
            messagebox.showerror("Missing dose", "Dose is required (e.g. 50 mg).")
            return

        t = simpledialog.askstring(
            "Log Vyvanse",
            "Time (blank = now). Examples: 'today 7:34am', '7:34am', ISO…",
            initialvalue="",
            parent=self,
        )
        if t is None:
            return

        notes = simpledialog.askstring("Log Vyvanse", "Notes (optional):", initialvalue="", parent=self)
        if notes is None:
            notes = ""

        try:
            ts = _parse_ts(t.strip())
        except Exception as e:
            messagebox.showerror("Bad time", str(e))
            return

        entry: dict[str, Any] = {"ts": ts, "name": "Vyvanse", "dose": dose}
        if notes.strip():
            entry["notes"] = notes.strip()

        data = self.store.load()
        data.setdefault("medications", []).append(entry)
        self.store.save(data)

        self._refresh_med_list()
        self._refresh_vyvanse_chip()

    # -------------------------
    # Mood tab
    # -------------------------

    def _build_mood_tab(self) -> None:
        left = ttk.Frame(self.tab_mood)
        right = ttk.Frame(self.tab_mood)
        left.pack(side="left", fill="y", padx=(0, 10))
        right.pack(side="right", fill="both", expand=True)

        ttk.Label(left, text="Add mood", font=("TkDefaultFont", 12, "bold")).pack(anchor="w", pady=(0, 8))

        self.mood_score = tk.IntVar(value=6)
        self.mood_time = tk.StringVar(value="today 9am")
        self.mood_tags = tk.StringVar()
        self.mood_notes = tk.StringVar()

        self.sleep_total = tk.StringVar()
        self.sleep_rem = tk.StringVar()
        self.sleep_deep = tk.StringVar()

        ttk.Label(left, text="Score (1–10)").pack(anchor="w")
        ttk.Spinbox(left, from_=1, to=10, textvariable=self.mood_score, width=6).pack(anchor="w", pady=(0, 8))

        self._labeled_entry(left, "Time (e.g. today 9am)", self.mood_time)
        self._labeled_entry(left, "Tags (comma/space)", self.mood_tags)
        self._labeled_entry(left, "Notes (optional)", self.mood_notes)

        ttk.Separator(left).pack(fill="x", pady=10)
        ttk.Label(left, text="Sleep (optional)").pack(anchor="w")
        self._labeled_entry(left, "Total (e.g. 7:53 or 473)", self.sleep_total)
        self._labeled_entry(left, "REM (e.g. 1:22 or 82)", self.sleep_rem)
        self._labeled_entry(left, "Deep (e.g. 0:13 or 13)", self.sleep_deep)

        ttk.Button(left, text="Add Mood", command=self._safe_cmd(self._mood_add)).pack(fill="x", pady=(8, 0))

        ttk.Separator(right).pack(fill="x", pady=(0, 8))
        ttk.Label(right, text="Mood log (newest first)", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")

        self.mood_list = tk.Listbox(right, height=20)
        self.mood_list.pack(fill="both", expand=True, pady=8)

        ttk.Button(
            right,
            text="Delete selected (careful)",
            command=self._safe_cmd(self._mood_delete_selected),
        ).pack(anchor="e")

    def _parse_tags(self, raw: str) -> list[str]:
        raw = raw.strip()
        if not raw:
            return []
        parts: list[str] = []
        for chunk in raw.replace(",", " ").split():
            c = chunk.strip()
            if c:
                parts.append(c)

        out: list[str] = []
        seen: set[str] = set()
        for p in parts:
            k = p.lower()
            if k in seen:
                continue
            seen.add(k)
            out.append(p)
        return out

    def _mood_add(self) -> None:
        score = int(self.mood_score.get())
        if not (1 <= score <= 10):
            messagebox.showerror("Bad score", "Mood score must be 1–10.")
            return

        t = self.mood_time.get().strip()
        try:
            ts = _parse_ts(t)
        except Exception as e:
            messagebox.showerror("Bad time", str(e))
            return

        entry: dict[str, Any] = {"ts": ts, "score": score}

        tags = self._parse_tags(self.mood_tags.get())
        if tags:
            entry["tags"] = tags

        notes = self.mood_notes.get().strip()
        if notes:
            entry["notes"] = notes

        try:
            st = _parse_minutes(self.sleep_total.get())
            sr = _parse_minutes(self.sleep_rem.get())
            sd = _parse_minutes(self.sleep_deep.get())
        except ValueError as e:
            messagebox.showerror("Bad sleep value", str(e))
            return

        if st is not None:
            entry["sleep_total_min"] = st
        if sr is not None:
            entry["sleep_rem_min"] = sr
        if sd is not None:
            entry["sleep_deep_min"] = sd

        data = self.store.load()
        data.setdefault("moods", []).append(entry)
        self.store.save(data)

        self.mood_tags.set("")
        self.mood_notes.set("")
        self.sleep_total.set("")
        self.sleep_rem.set("")
        self.sleep_deep.set("")
        self._refresh_mood_list()
        self._draw_mood_graph()

    def _mood_delete_selected(self) -> None:
        sel = self.mood_list.curselection()
        if not sel:
            return
        if not messagebox.askyesno("Confirm delete", "Delete selected mood entry? This cannot be undone."):
            return

        idx = sel[0]
        data = self.store.load()
        moods = data.get("moods", [])
        moods_sorted = sorted(moods, key=lambda m: str(m.get("ts", "")), reverse=True)
        if idx < 0 or idx >= len(moods_sorted):
            return
        target = moods_sorted[idx]

        for i, m in enumerate(moods):
            if m == target:
                moods.pop(i)
                break

        data["moods"] = moods
        self.store.save(data)
        self._refresh_mood_list()
        self._draw_mood_graph()

    def _refresh_mood_list(self) -> None:
        self.mood_list.delete(0, tk.END)
        data = self.store.load()
        moods = sorted(data.get("moods", []), key=lambda m: str(m.get("ts", "")), reverse=True)

        for m in moods:
            dt = _dt_from_entry_ts(str(m.get("ts", "")))
            when = f"{dt.date().isoformat()} {_fmt_time(dt)}" if dt else str(m.get("ts", ""))
            tags = m.get("tags", [])
            notes = m.get("notes", "")
            st = m.get("sleep_total_min")
            sr = m.get("sleep_rem_min")
            sd = m.get("sleep_deep_min")

            line = f"{when} — {m.get('score', '')}/10"
            if tags:
                line += f" [{', '.join(tags)}]"
            if st is not None or sr is not None or sd is not None:
                line += (
                    f" | sleep total={st if st is not None else '—'}"
                    f" rem={sr if sr is not None else '—'}"
                    f" deep={sd if sd is not None else '—'}"
                )
            if notes:
                line += f" | {notes}"
            self.mood_list.insert(tk.END, line)

    # -------------------------
    # Water goals (global default + per-day override)
    # -------------------------

    def _get_water_goal_for_day(self, day_key: str) -> int:
        data = self.store.load()
        daily_logs = data.get("daily_logs", {})
        if isinstance(daily_logs, dict):
            d = daily_logs.get(day_key)
            if isinstance(d, dict):
                g = d.get("water_goal_oz")
                if isinstance(g, (int, float)):
                    return int(g)
                if isinstance(g, str) and g.strip().isdigit():
                    return int(g.strip())

        g2 = data.get("water_goal_oz", 80)
        if isinstance(g2, (int, float)):
            return int(g2)
        if isinstance(g2, str) and g2.strip().isdigit():
            return int(g2.strip())
        return 80

    def _set_water_goal_for_day(self, day_key: str, goal_oz: int) -> None:
        data = self.store.load()
        if goal_oz < 0 or goal_oz > 512:
            raise ValueError("Goal must be a reasonable oz amount (0–512).")

        logs = data.setdefault("daily_logs", {})
        if not isinstance(logs, dict):
            logs = {}
            data["daily_logs"] = logs

        day_obj = logs.get(day_key)
        if not isinstance(day_obj, dict):
            day_obj = {}
            logs[day_key] = day_obj

        day_obj["water_goal_oz"] = int(goal_oz)
        self.store.save(data)

    def _set_default_water_goal(self, goal_oz: int) -> None:
        data = self.store.load()
        if goal_oz < 0 or goal_oz > 512:
            raise ValueError("Goal must be a reasonable oz amount (0–512).")
        data["water_goal_oz"] = int(goal_oz)
        self.store.save(data)

    # -------------------------
    # Water tab
    # -------------------------

    def _build_water_tab(self) -> None:
        left = ttk.Frame(self.tab_water)
        right = ttk.Frame(self.tab_water)
        left.pack(side="left", fill="y", padx=(0, 10))
        right.pack(side="right", fill="both", expand=True)

        ttk.Label(left, text="Water", font=("TkDefaultFont", 12, "bold")).pack(anchor="w", pady=(0, 8))

        # Quick add buttons
        btnrow = ttk.Frame(left)
        btnrow.pack(anchor="w", pady=(0, 8))

        ttk.Button(
            btnrow,
            text="+8 oz",
            command=self._safe_cmd(lambda: self._water_quick_add(8)),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            btnrow,
            text="+12 oz",
            command=self._safe_cmd(lambda: self._water_quick_add(12)),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            btnrow,
            text="+16 oz",
            command=self._safe_cmd(lambda: self._water_quick_add(16)),
        ).pack(side="left")

        ttk.Separator(left).pack(fill="x", pady=10)

        # Daily goal controls (for today)
        ttk.Label(left, text="Daily water goal (oz)").pack(anchor="w")

        self.water_goal_oz = tk.StringVar(value=str(self._get_water_goal_for_day(self._today_key())))
        goalrow = ttk.Frame(left)
        goalrow.pack(anchor="w", pady=(0, 8), fill="x")

        ttk.Entry(goalrow, textvariable=self.water_goal_oz, width=10).pack(side="left")
        ttk.Button(
            goalrow,
            text="Set for today",
            command=self._safe_cmd(self._water_set_goal_today),
        ).pack(side="left", padx=6)
        ttk.Button(
            goalrow,
            text="Set as default",
            command=self._safe_cmd(self._water_set_goal_default),
        ).pack(side="left")

        ttk.Separator(left).pack(fill="x", pady=10)

        # Custom add
        self.water_oz = tk.StringVar(value="8")
        self.water_time = tk.StringVar(value="")  # blank = now

        self._labeled_entry(left, "Amount (oz)", self.water_oz)
        self._labeled_entry(left, "Time (blank = now; e.g. today 2:10pm)", self.water_time)

        ttk.Button(left, text="Add Water", command=self._safe_cmd(self._water_add)).pack(fill="x", pady=(8, 0))

        # Right side: list + today chip
        ttk.Separator(right).pack(fill="x", pady=(0, 8))

        top = ttk.Frame(right)
        top.pack(fill="x")

        ttk.Label(top, text="Water log (newest first)", font=("TkDefaultFont", 12, "bold")).pack(side="left")

        self.water_today_chip = tk.StringVar(value="Today: 0 oz")
        ttk.Label(top, textvariable=self.water_today_chip, foreground="#444").pack(side="right")

        self.water_list = tk.Listbox(right, height=20)
        self.water_list.pack(fill="both", expand=True, pady=8)

        ttk.Button(
            right,
            text="Delete selected (careful)",
            command=self._safe_cmd(self._water_delete_selected),
        ).pack(anchor="e")

    def _water_set_goal_today(self) -> None:
        raw = self.water_goal_oz.get().strip()
        try:
            goal = int(float(raw))
        except Exception:
            messagebox.showerror("Bad goal", "Goal must be a number (oz). Example: 80.")
            return
        if goal < 0 or goal > 512:
            messagebox.showerror("Bad goal", "Please enter a reasonable goal (0–512 oz).")
            return

        self._set_water_goal_for_day(self._today_key(), goal)
        self._refresh_water_today_chip()

    def _water_set_goal_default(self) -> None:
        raw = self.water_goal_oz.get().strip()
        try:
            goal = int(float(raw))
        except Exception:
            messagebox.showerror("Bad goal", "Goal must be a number (oz). Example: 80.")
            return
        if goal < 0 or goal > 512:
            messagebox.showerror("Bad goal", "Please enter a reasonable goal (0–512 oz).")
            return

        self._set_default_water_goal(goal)
        # also set today's override to match (so the chip updates consistently)
        self._set_water_goal_for_day(self._today_key(), goal)
        self._refresh_water_today_chip()

    def _water_quick_add(self, oz: int) -> None:
        entry: dict[str, Any] = {
            "ts": _now_local().isoformat(timespec="seconds"),
            "oz": int(oz),
        }
        data = self.store.load()
        data.setdefault("water", []).append(entry)
        self.store.save(data)
        self._refresh_water_list()
        self._refresh_water_today_chip()

    def _water_add(self) -> None:
        raw_oz = self.water_oz.get().strip()
        raw_time = self.water_time.get().strip()

        try:
            oz = int(float(raw_oz))  # allows "8.0"
        except Exception:
            messagebox.showerror("Bad amount", "Water amount must be a number (oz). Example: 8 or 12.")
            return

        if oz <= 0 or oz > 256:
            messagebox.showerror("Bad amount", "Please enter a reasonable oz amount (1–256).")
            return

        try:
            ts = _parse_ts(raw_time)  # blank/today/now supported
        except Exception as e:
            messagebox.showerror("Bad time", str(e))
            return

        entry: dict[str, Any] = {"ts": ts, "oz": oz}

        data = self.store.load()
        data.setdefault("water", []).append(entry)
        self.store.save(data)

        self.water_oz.set("8")
        self.water_time.set("")

        self._refresh_water_list()
        self._refresh_water_today_chip()

    def _refresh_water_list(self) -> None:
        if not hasattr(self, "water_list"):
            return

        self.water_list.delete(0, tk.END)
        data = self.store.load()
        water = sorted(data.get("water", []), key=lambda w: str(w.get("ts", "")), reverse=True)

        for w in water:
            dt = _dt_from_entry_ts(str(w.get("ts", "")))
            when = f"{dt.date().isoformat()} {_fmt_time(dt)}" if dt else str(w.get("ts", ""))
            oz = w.get("oz", "")
            self.water_list.insert(tk.END, f"{when} — {oz} oz")

    def _water_delete_selected(self) -> None:
        if not hasattr(self, "water_list"):
            return
        sel = self.water_list.curselection()
        if not sel:
            return
        if not messagebox.askyesno("Confirm delete", "Delete selected water entry? This cannot be undone."):
            return

        idx = sel[0]
        data = self.store.load()
        water = data.get("water", [])
        water_sorted = sorted(water, key=lambda w: str(w.get("ts", "")), reverse=True)
        if idx < 0 or idx >= len(water_sorted):
            return
        target = water_sorted[idx]

        for i, w in enumerate(water):
            if w == target:
                water.pop(i)
                break

        data["water"] = water
        self.store.save(data)
        self._refresh_water_list()
        self._refresh_water_today_chip()

    def _water_total_today_oz(self) -> int:
        data = self.store.load()
        water = data.get("water", [])
        today = _now_local().date()
        total = 0

        for w in water:
            dt = _dt_from_entry_ts(str(w.get("ts", "")))
            if not dt:
                continue
            if dt.astimezone().date() == today:
                oz = w.get("oz")
                if isinstance(oz, (int, float)):
                    total += int(oz)
                elif isinstance(oz, str) and oz.strip().isdigit():
                    total += int(oz.strip())

        return total

    def _water_daily_totals(self, days: int) -> dict[str, int]:
        cutoff = _now_local().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)

        data = self.store.load()
        water = data.get("water", [])

        by_day: dict[str, int] = {}

        for w in water:
            dt = _dt_from_entry_ts(str(w.get("ts", "")))
            if not dt or dt < cutoff:
                continue

            oz = w.get("oz")
            n = 0
            if isinstance(oz, (int, float)):
                n = int(oz)
            elif isinstance(oz, str) and oz.strip().isdigit():
                n = int(oz.strip())

            if n <= 0:
                continue

            day = dt.date().isoformat()
            by_day[day] = by_day.get(day, 0) + n

        return by_day

    def _refresh_water_today_chip(self) -> None:
        if not hasattr(self, "water_today_chip"):
            return

        total = self._water_total_today_oz()
        goal = self._get_water_goal_for_day(self._today_key())

        if goal > 0:
            pct = int(round((total / goal) * 100)) if goal else 0
            self.water_today_chip.set(f"Today: {total}/{goal} oz ({pct}%)")
        else:
            self.water_today_chip.set(f"Today: {total} oz")

    # -------------------------
    # Stats tab + analysis
    # -------------------------

    def _build_stats_tab(self) -> None:
        top = ttk.Frame(self.tab_stats)
        top.pack(fill="x")

        ttk.Label(top, text="Stats", font=("TkDefaultFont", 12, "bold")).pack(side="left")
        self.stats_days = tk.IntVar(value=14)
        ttk.Label(top, text="Lookback days:").pack(side="left", padx=(20, 6))
        ttk.Spinbox(top, from_=1, to=365, textvariable=self.stats_days, width=6).pack(side="left")

        btns = ttk.Frame(self.tab_stats)
        btns.pack(fill="x", pady=10)

        ttk.Button(
            btns,
            text="Medication counts",
            command=self._safe_cmd(self._stats_med_counts),
        ).pack(side="left", padx=6)
        ttk.Button(
            btns,
            text="Mood daily averages",
            command=self._safe_cmd(self._stats_mood_daily),
        ).pack(side="left", padx=6)
        ttk.Button(btns, text="Water totals", command=self._safe_cmd(self._stats_water_totals)).pack(
            side="left", padx=6
        )

        graph_box = ttk.LabelFrame(self.tab_stats, text="Mood Graph (avg per day)")
        graph_box.pack(fill="x", padx=4, pady=6)

        controls = ttk.Frame(graph_box)
        controls.pack(fill="x", padx=6, pady=4)

        ttk.Label(controls, text="Days:").pack(side="left")
        self.graph_days = tk.IntVar(value=14)
        ttk.Spinbox(controls, from_=1, to=365, textvariable=self.graph_days, width=6).pack(side="left", padx=6)

        ttk.Button(
            controls,
            text="Refresh graph",
            command=self._safe_cmd(self._draw_mood_graph),
        ).pack(side="left", padx=6)
        ttk.Label(controls, text="Avg mood per day (1–10)").pack(side="right")

        self.graph_canvas = tk.Canvas(
            graph_box,
            height=160,
            bg="white",
            highlightthickness=1,
            highlightbackground="#ccc",
        )
        self.graph_canvas.pack(fill="x", padx=6, pady=(0, 6))
        self.graph_canvas.bind("<Configure>", self._schedule_graph_redraw)

        analysis_box = ttk.LabelFrame(self.tab_stats, text="Mood Analysis")
        analysis_box.pack(fill="x", padx=4, pady=6)

        row = ttk.Frame(analysis_box)
        row.pack(fill="x", padx=6, pady=4)

        ttk.Label(row, text="Range:").pack(side="left")
        self.analysis_range = tk.StringVar(value="Last 30 days")
        self.analysis_options = [
            "Last 7 days",
            "Last 14 days",
            "Last 30 days",
            "Last 90 days",
            "All time",
        ]
        ttk.Combobox(
            row,
            textvariable=self.analysis_range,
            values=self.analysis_options,
            width=16,
            state="readonly",
        ).pack(side="left", padx=6)
        ttk.Button(row, text="Analyze", command=self._safe_cmd(self._analyze_mood)).pack(side="left", padx=6)

        self.analysis_out = tk.Text(analysis_box, height=8, wrap="word")
        self.analysis_out.pack(fill="x", padx=6, pady=(0, 6))
        self._analysis_write("Mood Analysis\n----------------------------\nClick Analyze.")

        self.stats_out = tk.Text(self.tab_stats, wrap="word")
        self.stats_out.pack(fill="both", expand=True, pady=(8, 0))

    def _stats_water_totals(self) -> None:
        days = int(self.stats_days.get())
        cutoff = _now_local().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)

        data = self.store.load()
        water = data.get("water", [])

        by_day: dict[str, int] = {}
        total = 0

        for w in water:
            dt = _dt_from_entry_ts(str(w.get("ts", "")))
            if not dt or dt < cutoff:
                continue

            oz = w.get("oz")
            n = 0
            if isinstance(oz, (int, float)):
                n = int(oz)
            elif isinstance(oz, str) and oz.strip().isdigit():
                n = int(oz.strip())
            if n <= 0:
                continue

            day = dt.date().isoformat()
            by_day[day] = by_day.get(day, 0) + n
            total += n

        lines = [
            f"Water totals (last {days} days)",
            "-------------------------------",
            f"Total: {total} oz",
            "",
        ]

        if not by_day:
            lines.append("No entries.")
        else:
            # include goal if available for that day
            for d in sorted(by_day.keys()):
                goal = self._get_water_goal_for_day(d)
                if goal > 0:
                    pct = int(round((by_day[d] / goal) * 100))
                    lines.append(f"- {d}: {by_day[d]} / {goal} oz ({pct}%)")
                else:
                    lines.append(f"- {d}: {by_day[d]} oz")

        self._write_stats("\n".join(lines))

    def _stats_med_counts(self) -> None:
        days = int(self.stats_days.get())
        cutoff = _now_local().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)

        data = self.store.load()
        meds = data.get("medications", [])

        counts: dict[str, int] = {}
        for m in meds:
            dt = _dt_from_entry_ts(str(m.get("ts", "")))
            if not dt or dt < cutoff:
                continue
            name = str(m.get("name", "")).strip()
            if not name:
                continue
            key = name
            counts[key] = counts.get(key, 0) + 1

        lines = [
            f"Medication counts (last {days} days)",
            "------------------------------------",
        ]
        if not counts:
            lines.append("No entries.")
        else:
            for k in sorted(counts.keys(), key=lambda x: (-counts[x], x.lower())):
                lines.append(f"- {k}: {counts[k]}")

        self._write_stats("\n".join(lines))

    def _mood_daily_avgs(self, days: int) -> tuple[list[str], list[float]]:
        cutoff = _now_local().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
        data = self.store.load()
        moods = data.get("moods", [])

        by_day: dict[str, list[int]] = {}
        for m in moods:
            dt = _dt_from_entry_ts(str(m.get("ts", "")))
            if not dt or dt < cutoff:
                continue
            s = m.get("score")
            if isinstance(s, int) and 1 <= s <= 10:
                by_day.setdefault(dt.date().isoformat(), []).append(s)

        days_sorted = sorted(by_day.keys())
        avgs = [sum(by_day[d]) / len(by_day[d]) for d in days_sorted]
        return days_sorted, avgs

    def _analyze_water_vs_mood(self, days: int = 30) -> str:
        water_by_day = self._water_daily_totals(days)
        mood_days, mood_avgs = self._mood_daily_avgs(days)

        xs: list[float] = []
        ys: list[float] = []

        for d, mood in zip(mood_days, mood_avgs):
            if d in water_by_day:
                xs.append(float(water_by_day[d]))
                ys.append(float(mood))

        if len(xs) < 3:
            return "Not enough overlapping water + mood data yet."

        r = _pearson_corr(xs, ys)

        if r is None:
            return "Could not compute correlation."

        if r > 0.4:
            return f"Higher hydration appears linked to better mood (r={r:.2f})."
        if r < -0.4:
            return f"Unexpected pattern: more water linked to lower mood (r={r:.2f})."
        return f"Weak or no clear hydration–mood relationship (r={r:.2f})."

    def _stats_mood_daily(self) -> None:
        days = int(self.stats_days.get())
        ds, avgs = self._mood_daily_avgs(days)

        lines = [
            f"Mood daily averages (last {days} days)",
            "--------------------------------------",
        ]
        if not ds:
            lines.append("No entries.")
            self._write_stats("\n".join(lines))
            return

        overall = sum(avgs) / len(avgs)
        lines.append(f"Overall avg (days with entries): {overall:.2f}/10")
        lines.append("")
        for d, a in zip(ds, avgs):
            lines.append(f"- {d}: {a:.2f}/10")

        self._write_stats("\n".join(lines))

    def _daily_mood_series(self, days: int | None = 90) -> list[tuple[datetime, float]]:
        data = self.store.load()
        moods = data.get("moods", [])

        cutoff = None
        if days is not None:
            cutoff = _now_local().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)

        by_day: dict[datetime, list[int]] = {}
        for m in moods:
            dt = _dt_from_entry_ts(str(m.get("ts", "")))
            if not dt:
                continue
            day = dt.astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
            if cutoff and day < cutoff:
                continue
            s = m.get("score")
            if isinstance(s, int) and 1 <= s <= 10:
                by_day.setdefault(day, []).append(s)

        out: list[tuple[datetime, float]] = []
        for day in sorted(by_day.keys()):
            vals = by_day[day]
            out.append((day, sum(vals) / len(vals)))
        return out

    def _rolling_avg(self, values: list[float], window: int) -> list[float | None]:
        if window <= 0:
            raise ValueError("window must be > 0")
        out: list[float | None] = [None] * len(values)
        if len(values) < window:
            return out

        running = sum(values[:window])
        out[window - 1] = running / window
        for i in range(window, len(values)):
            running += values[i] - values[i - window]
            out[i] = running / window
        return out

    def _compute_baseline(
        self,
        series: list[tuple[datetime, float]],
        baseline_days: int = 30,
        exclude_recent_days: int = 3,
    ) -> float | None:
        if not series:
            return None

        if exclude_recent_days > 0 and len(series) > exclude_recent_days:
            baseline_pool = series[:-exclude_recent_days]
        else:
            baseline_pool = series[:]

        if not baseline_pool:
            return None

        pool = baseline_pool[-baseline_days:] if baseline_days and len(baseline_pool) > baseline_days else baseline_pool
        vals = [v for _, v in pool]
        if not vals:
            return None
        return sum(vals) / len(vals)

    def _detect_mood_alerts(
        self,
        lookback_days: int = 90,
        baseline_days: int = 30,
        exclude_recent_days: int = 3,
        dip_threshold: float = 1.0,
        crash_drop_day: float = 2.0,
        crash_drop_3day: float = 1.5,
        low_zone: float = 4.0,
        high_zone: float = 7.0,
    ) -> str:
        series = self._daily_mood_series(days=lookback_days)
        if len(series) < 5:
            return "Not enough mood data yet for alerts (need a few days of entries)."

        days = [d for d, _ in series]
        vals = [v for _, v in series]

        baseline = self._compute_baseline(series, baseline_days=baseline_days, exclude_recent_days=exclude_recent_days)
        r3 = self._rolling_avg(vals, 3)

        alerts: list[str] = []

        if baseline is not None:
            dip_events: list[tuple[datetime, float]] = []
            for i in range(len(vals)):
                avg3 = r3[i]
                if avg3 is None:
                    continue
                if avg3 <= baseline - dip_threshold:
                    dip_events.append((days[i], avg3))

            if dip_events:
                last_day, last_avg3 = dip_events[-1]
                ongoing = days[-1] == last_day
                status = "ONGOING" if ongoing else "RECENT"
                alerts.append(
                    f"⚠️  3-day dip vs baseline ({status})\n"
                    f"- Baseline (approx): {baseline:.2f}/10\n"
                    f"- Latest 3-day avg:  {last_avg3:.2f}/10 on {last_day.date().isoformat()}\n"
                    f"- Drop: {baseline - last_avg3:.2f} (threshold {dip_threshold:.2f})"
                )
            else:
                alerts.append(
                    f"✅ No 3-day dips below baseline detected.\n"
                    f"- Baseline (approx): {baseline:.2f}/10\n"
                    f"- Threshold: {dip_threshold:.2f}"
                )
        else:
            alerts.append("Baseline unavailable (not enough prior days).")

        crash_hits: list[str] = []

        for i in range(1, len(vals)):
            drop = vals[i - 1] - vals[i]
            if drop >= crash_drop_day:
                crash_hits.append(
                    f"- Day-to-day drop ≥ {crash_drop_day:.1f}: {days[i - 1].date().isoformat()} ({vals[i - 1]:.1f}) → "
                    f"{days[i].date().isoformat()} ({vals[i]:.1f}) [drop {drop:.1f}]"
                )

        for i in range(5, len(vals)):
            a_now = r3[i]
            a_prev = r3[i - 3]
            if a_now is None or a_prev is None:
                continue
            drop = a_prev - a_now
            if drop >= crash_drop_3day:
                crash_hits.append(
                    f"- 3-day avg drop ≥ {crash_drop_3day:.1f}: {days[i - 3].date().isoformat()} (avg {a_prev:.2f}) → "
                    f"{days[i].date().isoformat()} (avg {a_now:.2f}) [drop {drop:.2f}]"
                )

        for i in range(len(vals) - 2):
            if vals[i] >= high_zone and vals[i + 1] <= low_zone and vals[i + 2] <= low_zone:
                crash_hits.append(
                    f"- Low streak after high day: {days[i].date().isoformat()} ({vals[i]:.1f}) then "
                    f"{days[i + 1].date().isoformat()} ({vals[i + 1]:.1f}), "
                    f"{days[i + 2].date().isoformat()} ({vals[i + 2]:.1f})"
                )

        if crash_hits:
            crash_block = "💥 Emotional crash patterns detected\n" + "\n".join(crash_hits[-6:])
        else:
            crash_block = "✅ No clear emotional crash patterns detected (by current thresholds)."

        alerts.append(crash_block)

        guidance = (
            "\n\nNext-step suggestions (non-judgey):\n"
            "- If a dip is ongoing: lower cognitive load for 24–48h (tiny tasks, easy wins).\n"
            "- If crash hits show up: check sleep totals/REM/deep and stimulant overlap in that window.\n"
            "- Keep logging; the detector gets smarter as the dataset grows."
        )

        return "Mood Alerts\n----------------------------\n" + "\n\n".join(alerts) + guidance

    def _analyze_sleep_vs_mood(self, days: int = 30) -> str:
        data = self.store.load()
        moods = data.get("moods", [])
        cutoff = _now_local() - timedelta(days=days)

        sleep_vals: list[float] = []
        mood_vals: list[float] = []

        for m in moods:
            dt = _dt_from_entry_ts(str(m.get("ts", "")))
            if not dt or dt < cutoff:
                continue
            score = m.get("score")
            sleep_total = m.get("sleep_total_min")
            if isinstance(score, int) and sleep_total is not None:
                try:
                    mood_vals.append(float(score))
                    sleep_vals.append(float(sleep_total))
                except Exception:
                    continue

        if len(mood_vals) < 3:
            return "Not enough data yet to analyze sleep vs mood."

        r = _pearson_corr(sleep_vals, mood_vals)
        if r is None:
            return "Sleep vs mood correlation unavailable (data lacks variation)."

        direction = "positive" if r > 0 else "negative"
        strength = "weak"
        if abs(r) >= 0.6:
            strength = "strong"
        elif abs(r) >= 0.35:
            strength = "moderate"

        return f"Sleep vs mood correlation (last {days} days): r={r:+.2f} ({strength} {direction})."

    def _analyze_mood(self) -> None:
        window_label = self.analysis_range.get().strip()
        days: int | None
        if window_label == "All time":
            days = None
        else:
            try:
                days = int(window_label.split()[1])
            except Exception:
                days = 30

        data = self.store.load()
        moods = data.get("moods", [])

        cutoff = None
        if days is not None:
            cutoff = _now_local() - timedelta(days=days)

        scores: list[int] = []
        for m in moods:
            dt = _dt_from_entry_ts(str(m.get("ts", "")))
            if not dt:
                continue
            if cutoff is not None and dt < cutoff:
                continue
            s = m.get("score")
            if isinstance(s, int) and 1 <= s <= 10:
                scores.append(s)

        if not scores:
            self._analysis_write("Mood Analysis\n----------------------------\nNo mood entries in this range.")
            return

        avg = sum(scores) / len(scores)
        mn = min(scores)
        mx = max(scores)

        series = self._daily_mood_series(days=days if days is not None else 3650)
        if len(series) >= 3:
            vals = [v for _, v in series]
            xs = [float(i) for i in range(len(vals))]
            slope = _linear_regression_slope(xs, [float(v) for v in vals])
            trend_label = _trend_label_from_slope(slope, stable_band=0.02)
            trend_line = f"Trend: {trend_label} ({slope:+.2f}/day)\n"
        else:
            trend_line = "Trend: Not enough data for trend.\n"

        sleep_insight = self._analyze_sleep_vs_mood(days=30)
        water_insight = self._analyze_water_vs_mood(days if days is not None else 30)

        alerts_text = self._detect_mood_alerts(
            lookback_days=90,
            baseline_days=30,
            exclude_recent_days=3,
            dip_threshold=1.0,
            crash_drop_day=2.0,
            crash_drop_3day=1.5,
            low_zone=4.0,
            high_zone=7.0,
        )

        base_text = (
            "Mood Analysis\n----------------------------\n"
            f"Range: {window_label}\n\n"
            f"Entries: {len(scores)}\n"
            f"Average rating: {avg:.2f}\n"
            f"Min / Max: {mn} / {mx}\n"
            f"{trend_line}\n"
            f"{sleep_insight}\n"
            "\nHydration Insight\n----------------------------\n"
            f"{water_insight}\n"
        )

        self._analysis_write(base_text + "\n" + alerts_text)

    # -------------------------
    # Mood Graph Drawing
    # -------------------------

    def _schedule_graph_redraw(self, _evt=None) -> None:
        if self._graph_redraw_job is not None:
            try:
                self.after_cancel(self._graph_redraw_job)
            except Exception:
                pass
        self._graph_redraw_job = self.after(120, self._draw_mood_graph)

    def _graph_show_tooltip(self, _event, text: str) -> None:
        self._graph_hide_tooltip()

        tip = tk.Toplevel(self)
        tip.wm_overrideredirect(True)
        try:
            tip.attributes("-topmost", True)
        except Exception:
            pass

        label = tk.Label(
            tip,
            text=text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("TkDefaultFont", 9),
            padx=6,
            pady=4,
        )
        label.pack()

        x = self.winfo_pointerx() + 12
        y = self.winfo_pointery() - 10

        tip.update_idletasks()
        w = tip.winfo_width()
        h = tip.winfo_height()

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        if x + w > screen_w:
            x = screen_w - w - 10
        if y + h > screen_h:
            y = screen_h - h - 10
        if x < 0:
            x = 0
        if y < 0:
            y = 0

        tip.geometry(f"+{x}+{y}")
        self._graph_tooltip = tip

    def _graph_hide_tooltip(self, _event=None) -> None:
        tip = getattr(self, "_graph_tooltip", None)
        if tip is not None:
            try:
                tip.destroy()
            except Exception:
                pass
        self._graph_tooltip = None

    def _draw_mood_graph(self) -> None:
        if not hasattr(self, "graph_canvas") or not hasattr(self, "graph_days"):
            return

        days = int(self.graph_days.get())
        canvas = self.graph_canvas
        canvas.delete("all")

        data = self.store.load()
        moods = data.get("moods", [])

        cutoff = _now_local().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)

        by_day: dict[str, list[int]] = {}
        for m in moods:
            dt = _dt_from_entry_ts(str(m.get("ts", "")))
            if not dt or dt < cutoff:
                continue
            score = m.get("score")
            if isinstance(score, int) and 1 <= score <= 10:
                by_day.setdefault(dt.date().isoformat(), []).append(score)

        days_sorted = sorted(by_day.keys())
        daily_avgs: list[tuple[str, float, int, int, int]] = []
        for d in days_sorted:
            vals = by_day[d]
            if vals:
                avg = sum(vals) / len(vals)
                daily_avgs.append((d, avg, len(vals), min(vals), max(vals)))

        w = max(1, canvas.winfo_width())
        h = max(1, canvas.winfo_height())

        pad_l, pad_r, pad_t, pad_b = 40, 16, 14, 28
        plot_w = max(1, w - pad_l - pad_r)
        plot_h = max(1, h - pad_t - pad_b)

        if not daily_avgs:
            canvas.create_text(w // 2, h // 2, text="No mood data", fill="#666")
            return

        values = [avg for _, avg, _, _, _ in daily_avgs]
        xs = list(range(len(values)))
        slope = _linear_regression_slope([float(x) for x in xs], [float(y) for y in values])
        trend_label = _trend_label_from_slope(slope, stable_band=0.02)

        vmin, vmax = 1.0, 10.0
        zone_red_max = 4.0
        zone_yellow_max = 6.0

        def y_for(v: float) -> float:
            v = max(vmin, min(vmax, float(v)))
            span = max(1e-9, vmax - vmin)
            return pad_t + (vmax - v) * (plot_h / span)

        def x_for(i: int) -> float:
            n = len(values)
            if n <= 1:
                return pad_l + plot_w / 2
            return pad_l + (i * plot_w / (n - 1))

        y_red_top = y_for(zone_red_max)
        y_yellow_top = y_for(zone_yellow_max)
        y_top = y_for(vmax)
        y_bottom = y_for(vmin)

        canvas.create_rectangle(pad_l, y_red_top, w - pad_r, y_bottom, outline="", fill=MOOD_ZONE_RED)
        canvas.create_rectangle(pad_l, y_yellow_top, w - pad_r, y_red_top, outline="", fill=MOOD_ZONE_YELLOW)
        canvas.create_rectangle(pad_l, y_top, w - pad_r, y_yellow_top, outline="", fill=MOOD_ZONE_GREEN)

        canvas.create_line(pad_l, y_red_top, w - pad_r, y_red_top, fill="#dddddd")
        canvas.create_line(pad_l, y_yellow_top, w - pad_r, y_yellow_top, fill="#dddddd")

        for tick in (2, 4, 6, 8, 10):
            yy = y_for(float(tick))
            canvas.create_line(pad_l - 4, yy, pad_l, yy, fill="#444")
            canvas.create_text(pad_l - 8, yy, text=str(tick), anchor="e", fill="#444")

        canvas.create_line(pad_l, y_bottom, w - pad_r, y_bottom, fill="#444")

        def zone_color(v: float) -> str:
            if v < zone_red_max:
                return MOOD_LINE_RED
            if v < zone_yellow_max:
                return MOOD_LINE_YELLOW
            return MOOD_LINE_GREEN

        if len(values) >= 2:
            pts: list[float] = []
            for i, v in enumerate(values):
                pts.extend([x_for(i), y_for(v)])
            canvas.create_line(*pts, fill="#333", width=2)

        for i, (day, v, count, vmin_day, vmax_day) in enumerate(daily_avgs):
            x, y = x_for(i), y_for(v)

            dot = canvas.create_oval(
                x - 3,
                y - 3,
                x + 3,
                y + 3,
                outline="",
                fill=zone_color(v),
            )

            tooltip_text = f"{day}\nAvg: {v:.2f}/10\nEntries: {count}\nMin/Max: {vmin_day}/{vmax_day}"

            canvas.tag_bind(dot, "<Enter>", lambda e, t=tooltip_text: self._graph_show_tooltip(e, t))
            canvas.tag_bind(dot, "<Leave>", self._graph_hide_tooltip)

        first_day = daily_avgs[0][0]
        last_day = daily_avgs[-1][0]
        canvas.create_text(pad_l, h - 10, text=first_day, anchor="w", fill="#666")
        canvas.create_text(w - pad_r, h - 10, text=last_day, anchor="e", fill="#666")

        if len(values) >= 2:
            trend_txt = f"Trend: {trend_label} ({slope:+.2f}/day)"
            canvas.create_text(w - pad_r, pad_t, text=trend_txt, anchor="ne", fill="#666")

    # -------------------------
    # Export tab
    # -------------------------

    def _build_export_tab(self) -> None:
        box = ttk.Frame(self.tab_export)
        box.pack(fill="both", expand=True)

        ttk.Label(box, text="Export", font=("TkDefaultFont", 12, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            box,
            text="Exports your data file as-is (JSON). Useful for backups or sharing with Future You.",
            foreground="#555",
            wraplength=760,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        ttk.Button(box, text="Save JSON As…", command=self._safe_cmd(self._export_json_as)).pack(anchor="w")

        self.export_status = tk.StringVar(value="")
        ttk.Label(box, textvariable=self.export_status, foreground="#555").pack(anchor="w", pady=(8, 0))

    def _export_json_as(self) -> None:
        data = self.store.load()
        default_name = f"chaoscatcher-export-{_now_local().date().isoformat()}.json"

        path = filedialog.asksaveasfilename(
            title="Save ChaosCatcher JSON",
            defaultextension=".json",
            initialfile=default_name,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            save_json(Path(path), data)
        except Exception as e:
            messagebox.showerror("Export failed", f"Could not export JSON:\n{e}")
            return

        self.export_status.set(f"Saved: {path}")

    # -------------------------
    # Focus / Pomodoro tab
    # -------------------------

    def _build_focus_tab(self) -> None:
        left = ttk.Frame(self.tab_focus)
        right = ttk.Frame(self.tab_focus)
        left.pack(side="left", fill="y", padx=(0, 10))
        right.pack(side="right", fill="both", expand=True)

        ttk.Label(left, text="Focus / Pomodoro", font=("TkDefaultFont", 12, "bold")).pack(anchor="w", pady=(0, 8))

        ttk.Label(left, text="What are you working on?").pack(anchor="w")
        self.focus_task = tk.StringVar()
        task_row = ttk.Frame(left)
        task_row.pack(fill="x", pady=(0, 12))
        ttk.Entry(task_row, textvariable=self.focus_task, width=26).pack(
            side="left", fill="x", expand=True, padx=(0, 4)
        )
        ttk.Button(task_row, text="Set", width=4, command=self._safe_cmd(self._focus_set_task)).pack(side="left")

        # --- Timer display ---
        timer_frame = ttk.LabelFrame(left, text="Timer", padding=10)
        timer_frame.pack(fill="x", pady=(0, 8))

        self._focus_phase_var = tk.StringVar(value="Work")
        ttk.Label(timer_frame, textvariable=self._focus_phase_var, font=("TkDefaultFont", 11, "bold")).pack()

        self._focus_time_var = tk.StringVar(value="25:00")
        ttk.Label(timer_frame, textvariable=self._focus_time_var, font=("TkDefaultFont", 36, "bold")).pack()

        self._focus_session_var = tk.StringVar(value="Session 0/4")
        ttk.Label(timer_frame, textvariable=self._focus_session_var, foreground="#666").pack()

        # --- Buttons ---
        btn_row = ttk.Frame(left)
        btn_row.pack(fill="x", pady=(0, 12))

        self._focus_btn_var = tk.StringVar(value="▶ Start")
        ttk.Button(btn_row, textvariable=self._focus_btn_var, command=self._safe_cmd(self._focus_start_pause)).pack(
            side="left", expand=True, fill="x", padx=(0, 4)
        )
        ttk.Button(btn_row, text="⏭ Skip", command=self._safe_cmd(self._focus_skip)).pack(
            side="left", expand=True, fill="x", padx=(0, 4)
        )
        ttk.Button(btn_row, text="↺ Reset", command=self._safe_cmd(self._focus_reset)).pack(
            side="left", expand=True, fill="x"
        )

        ttk.Button(
            left, text="Test popup", command=self._safe_cmd(lambda: self._focus_notify("Test", "Popup is working!"))
        ).pack(fill="x", pady=(4, 0))

        # --- Settings ---
        ttk.Separator(left).pack(fill="x", pady=(8, 8))
        ttk.Label(left, text="Settings", font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(0, 4))

        self.focus_work_min = tk.IntVar(value=25)
        self.focus_short_break_min = tk.IntVar(value=5)
        self.focus_long_break_min = tk.IntVar(value=15)
        self.focus_sessions_before_long = tk.IntVar(value=4)

        grid = ttk.Frame(left)
        grid.pack(fill="x")
        for row, (label, var, lo, hi) in enumerate(
            [
                ("Work (min):", self.focus_work_min, 1, 60),
                ("Short break (min):", self.focus_short_break_min, 1, 30),
                ("Long break (min):", self.focus_long_break_min, 1, 60),
                ("Sessions/long break:", self.focus_sessions_before_long, 1, 10),
            ]
        ):
            ttk.Label(grid, text=label).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Spinbox(grid, from_=lo, to=hi, textvariable=var, width=5).grid(
                row=row, column=1, sticky="w", padx=(6, 0), pady=2
            )

        ttk.Button(left, text="Apply settings (resets timer)", command=self._safe_cmd(self._focus_reset)).pack(
            fill="x", pady=(8, 0)
        )

        # --- Right: session log ---
        ttk.Separator(right).pack(fill="x", pady=(0, 8))
        ttk.Label(right, text="Focus Session Log (newest first)", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")

        list_frame = ttk.Frame(right, relief="sunken", borderwidth=1)
        list_frame.pack(fill="both", expand=True, pady=8)
        self.focus_list = tk.Listbox(list_frame, height=18, borderwidth=0, highlightthickness=0)
        _focus_sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.focus_list.yview)
        self.focus_list.configure(yscrollcommand=_focus_sb.set)
        _focus_sb.pack(side="right", fill="y")
        self.focus_list.pack(side="left", fill="both", expand=True)

        export_row = ttk.Frame(right)
        export_row.pack(fill="x")
        ttk.Button(export_row, text="Export CSV", command=self._safe_cmd(self._focus_export_csv)).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(export_row, text="Export JSON", command=self._safe_cmd(self._focus_export_json)).pack(side="left")

        self._refresh_focus_list()

    # --- Timer helpers ---

    def _focus_seconds_for_phase(self) -> int:
        if self._focus_phase == "work":
            return int(self.focus_work_min.get()) * 60
        if self._focus_phase == "short_break":
            return int(self.focus_short_break_min.get()) * 60
        return int(self.focus_long_break_min.get()) * 60

    def _focus_phase_label(self) -> str:
        if self._focus_phase == "work":
            return "Work"
        if self._focus_phase == "short_break":
            return "Short Break"
        return "Long Break"

    def _focus_update_display(self) -> None:
        mins, secs = divmod(max(0, self._focus_seconds_left), 60)
        self._focus_time_var.set(f"{mins:02d}:{secs:02d}")

    def _focus_update_session_display(self) -> None:
        sessions_before = int(self.focus_sessions_before_long.get())
        self._focus_phase_var.set(self._focus_phase_label())
        self._focus_session_var.set(f"Session {self._focus_session_count}/{sessions_before}")

    # --- Timer actions ---

    def _focus_start_pause(self) -> None:
        if self._focus_running:
            self._focus_running = False
            if self._focus_job:
                try:
                    self.after_cancel(self._focus_job)
                except Exception:
                    pass
                self._focus_job = None
            self._focus_btn_var.set("▶ Start")
        else:
            if self._focus_phase == "work" and self._focus_session_start_ts is None:
                self._focus_session_start_ts = _now_local().isoformat(timespec="seconds")
            self._focus_running = True
            self._focus_btn_var.set("⏸ Pause")
            self._focus_job = self.after(1000, self._focus_tick)

    def _focus_tick(self) -> None:
        if not self._focus_running:
            return
        self._focus_seconds_left -= 1
        self._focus_update_display()
        if self._focus_seconds_left <= 0:
            self._focus_complete_phase()
        else:
            self._focus_job = self.after(1000, self._focus_tick)

    def _focus_complete_phase(self) -> None:
        self._focus_running = False
        self._focus_job = None
        self.bell()

        if self._focus_phase == "work":
            self._focus_session_count += 1
            self._focus_log_session(completed=True)
            self._focus_session_start_ts = None

            sessions_before = int(self.focus_sessions_before_long.get())
            if self._focus_session_count >= sessions_before:
                self._focus_phase = "long_break"
                self._focus_session_count = 0
                self._focus_notify("Work session done!", "Starting long break — take a real rest.")
            else:
                self._focus_phase = "short_break"
                self._focus_notify("Work session done!", "Starting short break.")

            # Auto-start the break
            self._focus_seconds_left = self._focus_seconds_for_phase()
            self._focus_update_display()
            self._focus_update_session_display()
            self._focus_running = True
            self._focus_btn_var.set("⏸ Pause")
            self._focus_job = self.after(1000, self._focus_tick)
        else:
            # Break done — return to work, don't auto-start
            self._focus_phase = "work"
            self._focus_seconds_left = self._focus_seconds_for_phase()
            self._focus_update_display()
            self._focus_update_session_display()
            self._focus_btn_var.set("▶ Start")
            self._focus_notify("Break over!", "Press Start when you're ready to focus.")

        self._refresh_focus_list()

    def _focus_notify(self, title: str, body: str) -> None:
        popup = tk.Toplevel(self)
        popup.title(title)
        popup.resizable(False, False)
        popup.attributes("-topmost", True)

        ttk.Label(popup, text=title, font=("TkDefaultFont", 13, "bold"), padding=(20, 16, 20, 4)).pack()
        ttk.Label(popup, text=body, padding=(20, 0, 20, 12)).pack()
        ttk.Button(popup, text="OK", command=popup.destroy, width=10).pack(pady=(0, 16))

        popup.update_idletasks()
        w, h = popup.winfo_width(), popup.winfo_height()
        sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
        popup.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")
        popup.grab_set()
        popup.focus_force()

    def _focus_skip(self) -> None:
        if self._focus_job:
            try:
                self.after_cancel(self._focus_job)
            except Exception:
                pass
            self._focus_job = None
        self._focus_running = False

        if self._focus_phase == "work":
            if self._focus_session_start_ts is not None:
                self._focus_log_session(completed=False)
                self._focus_session_start_ts = None
            self._focus_phase = "short_break"
        else:
            self._focus_phase = "work"

        self._focus_seconds_left = self._focus_seconds_for_phase()
        self._focus_btn_var.set("▶ Start")
        self._focus_update_display()
        self._focus_update_session_display()
        self._refresh_focus_list()

    def _focus_reset(self) -> None:
        if self._focus_job:
            try:
                self.after_cancel(self._focus_job)
            except Exception:
                pass
            self._focus_job = None
        self._focus_running = False

        if self._focus_phase == "work" and self._focus_session_start_ts is not None:
            self._focus_log_session(completed=False)
            self._focus_session_start_ts = None

        self._focus_phase = "work"
        self._focus_session_count = 0
        self._focus_seconds_left = int(self.focus_work_min.get()) * 60
        self._focus_btn_var.set("▶ Start")
        self._focus_update_display()
        self._focus_update_session_display()
        self._refresh_focus_list()

    def _focus_set_task(self) -> None:
        current = self.focus_task.get().strip()
        val = simpledialog.askstring(
            "Set task",
            "What are you working on?",
            initialvalue=current,
            parent=self,
        )
        if val is not None:
            self.focus_task.set(val.strip())

    # --- Session logging ---

    def _focus_log_session(self, completed: bool) -> None:
        if self._focus_session_start_ts is None:
            return

        full_secs = int(self.focus_work_min.get()) * 60
        if completed:
            duration_min = int(self.focus_work_min.get())
        else:
            elapsed_secs = full_secs - self._focus_seconds_left
            if elapsed_secs < 60:
                return  # don't log sessions under 1 minute
            duration_min = elapsed_secs // 60

        entry: dict[str, Any] = {
            "ts": self._focus_session_start_ts,
            "task": self.focus_task.get().strip(),
            "type": "work",
            "duration_min": duration_min,
            "completed": completed,
        }
        data = self.store.load()
        data.setdefault("focus_sessions", []).append(entry)
        self.store.save(data)

    # --- Session list ---

    def _refresh_focus_list(self) -> None:
        if not hasattr(self, "focus_list"):
            return
        self.focus_list.delete(0, tk.END)
        data = self.store.load()
        sessions = sorted(
            data.get("focus_sessions", []),
            key=lambda s: str(s.get("ts", "")),
            reverse=True,
        )
        for s in sessions:
            dt = _dt_from_entry_ts(str(s.get("ts", "")))
            when = f"{dt.date().isoformat()} {_fmt_time(dt)}" if dt else str(s.get("ts", ""))
            task = str(s.get("task", "")).strip() or "—"
            dur = s.get("duration_min", 0)
            done = "✓" if s.get("completed") else "✗"
            self.focus_list.insert(tk.END, f"{when}  {done} {dur}m — {task}")

    # --- Export ---

    _FOCUS_CSV_FIELDS = ["ts", "date", "time", "task", "type", "duration_min", "completed"]

    def _focus_export_csv(self) -> None:
        data = self.store.load()
        sessions = data.get("focus_sessions", [])

        rows: list[dict[str, Any]] = []
        for s in sessions:
            ts = str(s.get("ts", "")).strip()
            dt = _dt_from_entry_ts(ts)
            rows.append(
                {
                    "ts": ts,
                    "date": dt.date().isoformat() if dt else "",
                    "time": dt.strftime("%H:%M") if dt else "",
                    "task": str(s.get("task", "")).strip(),
                    "type": str(s.get("type", "work")),
                    "duration_min": s.get("duration_min", 0),
                    "completed": s.get("completed", False),
                }
            )
        rows.sort(key=lambda r: str(r["ts"]), reverse=True)

        default_name = f"focus-sessions-{_now_local().date().isoformat()}.csv"
        path = filedialog.asksaveasfilename(
            title="Export Focus Sessions CSV",
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            out = Path(path)
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=self._FOCUS_CSV_FIELDS, quoting=csv.QUOTE_MINIMAL)
                w.writeheader()
                w.writerows(rows)
            messagebox.showinfo("Exported", f"Saved {len(rows)} sessions → {path}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def _focus_export_json(self) -> None:
        data = self.store.load()
        sessions = sorted(
            data.get("focus_sessions", []),
            key=lambda s: str(s.get("ts", "")),
            reverse=True,
        )

        default_name = f"focus-sessions-{_now_local().date().isoformat()}.json"
        path = filedialog.asksaveasfilename(
            title="Export Focus Sessions JSON",
            defaultextension=".json",
            initialfile=default_name,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            out = Path(path)
            out.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps({"focus_sessions": sessions}, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
            out.write_text(payload, encoding="utf-8")
            messagebox.showinfo("Exported", f"Saved {len(sessions)} sessions → {path}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))


# -------------------------
# GUI Entrypoint
# -------------------------


def run_gui(argv=None) -> None:
    data_path = resolve_data_path(None, None)
    assert_safe_data_path(data_path, allow_repo_data_path=False)
    app = ChaosCatcherApp(Store(data_path))
    app.mainloop()


if __name__ == "__main__":
    run_gui()
