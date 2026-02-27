from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .paths import resolve_data_path
from .safety import assert_safe_data_path
from .storage import load_json, save_json
from .timeparse import parse_ts


# -------------------------
# Shared helpers
# -------------------------

def _now_local() -> datetime:
    return datetime.now().astimezone()


def _fmt_time(dt: datetime) -> str:
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
        dt = parse_ts(raw)
    except BaseException as e:
        raise ValueError(
            "Could not parse time. Try: '7:34am', 'today 7:34am', 'yesterday 9am', "
            "or ISO like '2026-02-25T07:34:00-05:00'."
        ) from e

    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception as e:
            raise ValueError(f"Could not parse time: {value!r}") from e

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_now_local().tzinfo)

    return dt.astimezone().isoformat(timespec="seconds")

def _default_daily_med_list() -> list[dict[str, str]]:
    """
    Default daily meds template.
    Edit this list in code OR use the GUI button to set it into your data file.
    Each item: {"name": "...", "dose": "...", "notes": "..."} (notes optional)
    """
    return [
        # Example:
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

        self._build_header()
        self._build_tabs()
        self._refresh_all_lists()

        self.after(120, self._draw_mood_graph)

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

    # -------- Header --------

    def _build_header(self) -> None:
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="x")

        ttk.Label(frm, text="ChaosCatcher", font=("TkDefaultFont", 16, "bold")).pack(side="left")

        self.path_var = tk.StringVar(value=str(self.store.data_path))
        ttk.Label(frm, textvariable=self.path_var, foreground="#666").pack(side="left", padx=12)

        btns = ttk.Frame(frm)
        btns.pack(side="right")

        ttk.Button(btns, text="Refresh", command=self._safe_cmd(self._refresh_all_lists)).pack(side="left", padx=4)
        ttk.Button(btns, text="Open Data Folder", command=self._safe_cmd(self._open_data_folder)).pack(side="left", padx=4)

    def _open_data_folder(self) -> None:
        messagebox.showinfo(
            "Data location",
            f"Data file:\n{self.store.data_path}\n\nOpen it with your file manager if you want.",
        )

    # -------- Tabs --------

    def _build_tabs(self) -> None:
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_med = ttk.Frame(self.nb, padding=10)
        self.tab_mood = ttk.Frame(self.nb, padding=10)
        self.tab_stats = ttk.Frame(self.nb, padding=10)
        self.tab_export = ttk.Frame(self.nb, padding=10)

        self.nb.add(self.tab_med, text="Medication")
        self.nb.add(self.tab_mood, text="Mood")
        self.nb.add(self.tab_stats, text="Stats")
        self.nb.add(self.tab_export, text="Export")

        self._build_med_tab()
        self._build_mood_tab()
        self._build_stats_tab()
        self._build_export_tab()
    # -------- Medication tab --------
  

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
        ttk.Button(left, text="Took all daily meds", command=self._safe_cmd(self._med_take_all)).pack(fill="x", pady=(6, 0))

        ttk.Separator(right).pack(fill="x", pady=(0, 8))
        ttk.Label(right, text="Medication log (newest first)", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")

        self.med_list = tk.Listbox(right, height=20)
        self.med_list.pack(fill="both", expand=True, pady=8)

        ttk.Button(right, text="Delete selected (careful)", command=self._safe_cmd(self._med_delete_selected)).pack(anchor="e")

   

    # -------- Mood tab --------

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

        ttk.Button(right, text="Delete selected (careful)", command=self._safe_cmd(self._mood_delete_selected)).pack(anchor="e")

    # -------- Stats tab --------

    def _build_stats_tab(self) -> None:
        top = ttk.Frame(self.tab_stats)
        top.pack(fill="x")

        ttk.Label(top, text="Stats", font=("TkDefaultFont", 12, "bold")).pack(side="left")
        self.stats_days = tk.IntVar(value=14)
        ttk.Label(top, text="Lookback days:").pack(side="left", padx=(20, 6))
        ttk.Spinbox(top, from_=1, to=365, textvariable=self.stats_days, width=6).pack(side="left")

        btns = ttk.Frame(self.tab_stats)
        btns.pack(fill="x", pady=10)
        ttk.Button(btns, text="Medication counts", command=self._safe_cmd(self._stats_med_counts)).pack(side="left", padx=6)
        ttk.Button(btns, text="Mood daily averages", command=self._safe_cmd(self._stats_mood_daily)).pack(side="left", padx=6)

        graph_box = ttk.LabelFrame(self.tab_stats, text="Mood Graph (avg per day)")
        graph_box.pack(fill="x", padx=4, pady=6)

        controls = ttk.Frame(graph_box)
        controls.pack(fill="x", padx=6, pady=4)

        ttk.Label(controls, text="Days:").pack(side="left")
        self.graph_days = tk.IntVar(value=14)
        ttk.Spinbox(controls, from_=1, to=365, textvariable=self.graph_days, width=6).pack(side="left", padx=6)

        ttk.Button(controls, text="Refresh graph", command=self._safe_cmd(self._draw_mood_graph)).pack(side="left", padx=6)
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
        self.analysis_options = ["Last 7 days", "Last 14 days", "Last 30 days", "Last 90 days", "All time"]
        ttk.Combobox(
            row,
            textvariable=self.analysis_range,
            values=self.analysis_options,
            width=16,
            state="readonly",
        ).pack(side="left", padx=6)
        ttk.Button(row, text="Analyze", command=self._safe_cmd(self._analyze_mood)).pack(side="left", padx=6)

        self.analysis_out = tk.Text(analysis_box, height=6, wrap="word")
        self.analysis_out.pack(fill="x", padx=6, pady=(0, 6))
        self._analysis_write("Mood Analysis\n----------------------------\nClick Analyze.")

        self.stats_out = tk.Text(self.tab_stats, wrap="word")
        self.stats_out.pack(fill="both", expand=True, pady=(8, 0))

    # -------- Export tab --------

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

    # -------- Helpers --------

    def _labeled_entry(self, parent: ttk.Frame, label: str, var: tk.StringVar) -> None:
        ttk.Label(parent, text=label).pack(anchor="w")
        ttk.Entry(parent, textvariable=var, width=30).pack(anchor="w", pady=(0, 8))

    def _refresh_all_lists(self) -> None:
        self._refresh_med_list()
        self._refresh_mood_list()
        self._draw_mood_graph()

    # -------- Medication actions --------

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
            ts = _parse_ts(t)  # blank/today/now supported
        except Exception as e:
            messagebox.showerror("Bad time", str(e))
            return

        entry: dict[str, Any] = {"ts": ts, "name": name, "dose": dose}
        if notes:
            entry["notes"] = notes

        data = self.store.load()
        meds = data.setdefault("medications", [])
        meds.append(entry)
        self.store.save(data)

        # clear inputs
        self.med_name.set("")
        self.med_dose.set("")
        self.med_time.set("")
        self.med_notes.set("")

        self._refresh_med_list()

    def _med_take_all(self) -> None:
        """
        Logs every item in data["daily_med_list"] as a medication entry at the current timestamp.
        """
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
        meds_sorted = list(reversed(meds))
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

    def _refresh_med_list(self) -> None:
        self.med_list.delete(0, tk.END)
        data = self.store.load()
        meds = list(reversed(data.get("medications", [])))

        for m in meds:
            dt = _dt_from_entry_ts(str(m.get("ts", "")))
            when = f"{dt.date().isoformat()} {_fmt_time(dt)}" if dt else str(m.get("ts", ""))
            notes = m.get("notes", "")
            line = f"{when} — {m.get('name','')} {m.get('dose','')}"
            if notes:
                line += f"  |  {notes}"
            self.med_list.insert(tk.END, line)

    # -------- Mood actions --------

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
        ts = _parse_ts(t)

        entry: dict[str, Any] = {"ts": ts, "score": score}

        tags = self._parse_tags(self.mood_tags.get())
        if tags:
            entry["tags"] = tags

        notes = self.mood_notes.get().strip()
        if notes:
            entry["notes"] = notes

        st = _parse_minutes(self.sleep_total.get())
        sr = _parse_minutes(self.sleep_rem.get())
        sd = _parse_minutes(self.sleep_deep.get())

        if st is not None:
            entry["sleep_total_min"] = st
        if sr is not None:
            entry["sleep_rem_min"] = sr
        if sd is not None:
            entry["sleep_deep_min"] = sd

        data = self.store.load()
        moods = data.setdefault("moods", [])
        moods.append(entry)
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
        moods_sorted = list(reversed(moods))
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
        moods = list(reversed(data.get("moods", [])))

        for m in moods:
            dt = _dt_from_entry_ts(str(m.get("ts", "")))
            when = f"{dt.date().isoformat()} {_fmt_time(dt)}" if dt else str(m.get("ts", ""))
            tags = m.get("tags", [])
            notes = m.get("notes", "")
            st = m.get("sleep_total_min")
            sr = m.get("sleep_rem_min")
            sd = m.get("sleep_deep_min")

            line = f"{when} — {m.get('score','')}/10"
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

    # -------- Stats actions --------

    def _write_stats(self, text: str) -> None:
        self.stats_out.delete("1.0", tk.END)
        self.stats_out.insert(tk.END, text)

    def _stats_med_counts(self) -> None:
        days = int(self.stats_days.get())
        cutoff = _now_local().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)

        data = self.store.load()
        meds = data.get("medications", [])

        counts: dict[str, int] = {}
        total = 0
        for m in meds:
            dt = _dt_from_entry_ts(str(m.get("ts", "")))
            if not dt or dt < cutoff:
                continue
            name = str(m.get("name", "")).strip() or "(unnamed)"
            counts[name] = counts.get(name, 0) + 1
            total += 1

        lines = [
            f"Medication counts (last {days} days)",
            "------------------------------------",
            f"Total entries: {total}",
            "",
        ]
        if not counts:
            lines.append("No entries.")
        else:
            for name, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower())):
                lines.append(f"- {name}: {n}")

        self._write_stats("\n".join(lines))

    def _stats_mood_daily(self) -> None:
        days = int(self.stats_days.get())
        day_labels, avgs = self._mood_daily_avgs(days)

        lines = [
            f"Mood daily averages (last {days} days)",
            "--------------------------------------",
        ]
        if not day_labels:
            lines.append("No entries.")
            self._write_stats("\n".join(lines))
            return

        overall = sum(avgs) / len(avgs)
        lines += ["", f"Days with entries: {len(avgs)}", f"Overall average: {overall:.2f}/10", ""]
        for d, a in zip(day_labels, avgs):
            lines.append(f"- {d}: {a:.2f}/10")

        self._write_stats("\n".join(lines))

    def _analysis_write(self, text: str) -> None:
        self.analysis_out.delete("1.0", tk.END)
        self.analysis_out.insert(tk.END, text)

    def _range_to_days(self) -> int | None:
        label = self.analysis_range.get()
        if label == "Last 7 days":
            return 7
        if label == "Last 14 days":
            return 14
        if label == "Last 30 days":
            return 30
        if label == "Last 90 days":
            return 90
        if label == "All time":
            return None
        return 30

    def _analyze_sleep_vs_mood(self, days: int = 30) -> str:
        """Compute Pearson correlation between sleep total and mood score."""
        data = self.store.load()
        moods = data.get("moods", [])

        cutoff = _now_local().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)

        mood_vals: list[float] = []
        sleep_vals: list[float] = []

        for m in moods:
            dt = _dt_from_entry_ts(str(m.get("ts", "")))
            if not dt or dt < cutoff:
                continue

            score = m.get("score")
            sleep_total = m.get("sleep_total_min")

            if isinstance(score, int) and sleep_total is not None:
                mood_vals.append(float(score))
                sleep_vals.append(float(sleep_total))

        if len(mood_vals) < 3:
            return "Not enough data yet to analyze sleep vs mood."

        import math

        mean_sleep = sum(sleep_vals) / len(sleep_vals)
        mean_mood = sum(mood_vals) / len(mood_vals)

        num = sum((s - mean_sleep) * (m - mean_mood) for s, m in zip(sleep_vals, mood_vals))
        den_sleep = math.sqrt(sum((s - mean_sleep) ** 2 for s in sleep_vals))
        den_mood = math.sqrt(sum((m - mean_mood) ** 2 for m in mood_vals))

        if den_sleep == 0 or den_mood == 0:
            return "Sleep or mood variance too small to analyze."

        r = num / (den_sleep * den_mood)

        if r > 0.4:
            return f"Stronger sleep appears linked to better mood (r={r:.2f})."
        elif r < -0.4:
            return f"Unexpected pattern: more sleep linked to lower mood (r={r:.2f})."
        else:
            return f"Weak or no clear sleep-mood relationship detected (r={r:.2f})."

    def _analyze_mood(self) -> None:
        days = self._range_to_days()
        data = self.store.load()
        moods = data.get("moods", [])

        sleep_insight = self._analyze_sleep_vs_mood(days if days is not None else 30)

        cutoff = None
        if days is not None:
            cutoff = _now_local().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)

        scores: list[int] = []
        for m in moods:
            dt = _dt_from_entry_ts(str(m.get("ts", "")))
            if not dt:
                continue
            if cutoff and dt < cutoff:
                continue
            s = m.get("score")
            if isinstance(s, int) and 1 <= s <= 10:
                scores.append(s)

        window_label = self.analysis_range.get()
        if not scores:
            self._analysis_write(
                "Mood Analysis\n----------------------------\n"
                f"Range: {window_label}\n\n"
                "No entries."
            )
            return

        avg = sum(scores) / len(scores)
        mn = min(scores)
        mx = max(scores)

        base_text: str = (
            "Mood Analysis\n----------------------------\n"
            f"Range: {window_label}\n\n"
            f"Entries: {len(scores)}\n"
            f"Average rating: {avg:.2f}\n"
            f"Min / Max: {mn} / {mx}\n\n"
            f"Sleep vs mood: {sleep_insight}\n"
        )

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

        self._analysis_write(base_text + "\n" + alerts_text)

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

    # -------------------------
    # Mood pattern detection
    # -------------------------

    def _daily_mood_series(self, days: int | None = 90) -> list[tuple[datetime, float]]:
        """
        Returns list of (day_start_local_datetime, avg_mood_for_day) sorted by day ascending.
        Only includes days that have entries.
        """
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
        """
        Returns rolling averages aligned to the same indices as values.
        Indices < window-1 => None.
        """
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

    def _compute_baseline(self, series: list[tuple[datetime, float]], baseline_days: int = 30, exclude_recent_days: int = 3) -> float | None:
        """
        Baseline = average of daily averages over baseline_days, excluding most recent exclude_recent_days.
        Returns None if insufficient data.
        """
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
        """
        Detect:
          - 3-day rolling avg dips below baseline by >= dip_threshold
          - crash patterns: big day-to-day drop, big 3-day drop, low streak after high day
        """
        series = self._daily_mood_series(days=lookback_days)
        if len(series) < 5:
            return "Not enough mood data yet for alerts (need a few days of entries)."

        days = [d for d, _ in series]
        vals = [v for _, v in series]

        baseline = self._compute_baseline(series, baseline_days=baseline_days, exclude_recent_days=exclude_recent_days)

        r3 = self._rolling_avg(vals, 3)

        alerts: list[str] = []

        # --- 3-day dip vs baseline ---
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
                ongoing = (days[-1] == last_day)
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

        # --- Crash patterns ---
        crash_hits: list[str] = []

        for i in range(1, len(vals)):
            drop = vals[i - 1] - vals[i]
            if drop >= crash_drop_day:
                crash_hits.append(
                    f"- Day-to-day drop ≥ {crash_drop_day:.1f}: {days[i-1].date().isoformat()} ({vals[i-1]:.1f}) → {days[i].date().isoformat()} ({vals[i]:.1f}) [drop {drop:.1f}]"
                )

        for i in range(5, len(vals)):
            a_now = r3[i]
            a_prev = r3[i - 3]
            if a_now is None or a_prev is None:
                continue
            drop = a_prev - a_now
            if drop >= crash_drop_3day:
                crash_hits.append(
                    f"- 3-day avg drop ≥ {crash_drop_3day:.1f}: {days[i-3].date().isoformat()} (avg {a_prev:.2f}) → {days[i].date().isoformat()} (avg {a_now:.2f}) [drop {drop:.2f}]"
                )

        for i in range(len(vals) - 2):
            if vals[i] >= high_zone and vals[i + 1] <= low_zone and vals[i + 2] <= low_zone:
                crash_hits.append(
                    f"- Low streak after high day: {days[i].date().isoformat()} ({vals[i]:.1f}) then "
                    f"{days[i+1].date().isoformat()} ({vals[i+1]:.1f}), {days[i+2].date().isoformat()} ({vals[i+2]:.1f})"
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

    # -------- Mood Graph Drawing --------

    def _schedule_graph_redraw(self, _evt=None) -> None:
        if self._graph_redraw_job is not None:
            try:
                self.after_cancel(self._graph_redraw_job)
            except Exception:
                pass
        self._graph_redraw_job = self.after(120, self._draw_mood_graph)

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
        daily_avgs: list[tuple[str, float]] = []
        for d in days_sorted:
            vals = by_day[d]
            if vals:
                daily_avgs.append((d, sum(vals) / len(vals)))

        w = max(1, canvas.winfo_width())
        h = max(1, canvas.winfo_height())

        pad_l, pad_r, pad_t, pad_b = 40, 16, 14, 28
        plot_w = max(1, w - pad_l - pad_r)
        plot_h = max(1, h - pad_t - pad_b)

        if not daily_avgs:
            canvas.create_text(w // 2, h // 2, text="No mood data", fill="#666")
            return

        values = [avg for _, avg in daily_avgs]
        xs = list(range(len(values)))
        slope = _linear_regression_slope([float(x) for x in xs], [float(y) for y in values])

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

        if len(values) == 1:
            x0 = x_for(0)
            y0 = y_for(values[0])
            canvas.create_oval(x0 - 3, y0 - 3, x0 + 3, y0 + 3, outline="", fill=zone_color(values[0]))
        else:
            for i in range(len(values) - 1):
                v1, v2 = values[i], values[i + 1]
                x1, y1 = x_for(i), y_for(v1)
                x2, y2 = x_for(i + 1), y_for(v2)
                canvas.create_line(x1, y1, x2, y2, width=2, fill=zone_color((v1 + v2) / 2.0))
            for i, v in enumerate(values):
                x, y = x_for(i), y_for(v)
                canvas.create_oval(x - 3, y - 3, x + 3, y + 3, outline="", fill=zone_color(v))

        first_day = daily_avgs[0][0]
        last_day = daily_avgs[-1][0]
        canvas.create_text(pad_l, h - 10, text=first_day, anchor="w", fill="#666")
        canvas.create_text(w - pad_r, h - 10, text=last_day, anchor="e", fill="#666")

        if len(values) >= 2:
            if slope > 0.02:
                trend_txt = f"Trend: +{slope:.2f}/day"
            elif slope < -0.02:
                trend_txt = f"Trend: {slope:.2f}/day"
            else:
                trend_txt = "Trend: ~flat"
            canvas.create_text(w - pad_r, pad_t, text=trend_txt, anchor="ne", fill="#666")


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