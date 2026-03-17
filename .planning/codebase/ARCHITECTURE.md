# Architecture

**Analysis Date:** 2026-03-16

## Pattern Overview

**Overall:** Layered monolith with shared utility layer serving dual interfaces (CLI + PySide6 GUI).

**Key Characteristics:**
- Entry/record-based data model (medications, moods, fuel/water, sleep, focus)
- Pure-function nudge engine (regulates promotion of fuel/hydration reminders)
- Flat-file JSON storage with safety guards
- Two entry points: command-line (`cli.py`) and desktop GUI (`gui.py`)
- Single-threaded event loop (QTimer for background tasks)
- No external API integrations or databases

## Layers

**Presentation (UI):**
- Purpose: Render and receive user input via Qt (GUI) or argparse (CLI)
- Location: `src/chaoscatcher/gui.py` (PySide6), `src/chaoscatcher/cli.py` (argparse + stdout)
- Contains: QMainWindow, QTabWidget, QDialog subclasses, entry forms, charts
- Depends on: Storage, utility, fuel_engine, notification_popup
- Used by: User interaction

**Application Logic:**
- Purpose: Handle data entry, validation, state transitions, calculations
- Location: `src/chaoscatcher/gui.py` (ChaosCatcherApp class methods), `src/chaoscatcher/cli.py` (cmd_* functions)
- Contains: Tab builders, refresh methods, mood analysis, stats calculation, CSV export
- Depends on: Storage, _util, timeparse, fuel_engine
- Used by: Presentation layer

**Domain (Business Rules):**
- Purpose: Pure, testable logic for nudge evaluation and statistics
- Location: `src/chaoscatcher/fuel_engine.py`
- Contains: FuelConfig, FuelStats, compute_fuel_stats(), evaluate_nudges()
- Depends on: _util (time helpers)
- Used by: Application logic

**Data Access:**
- Purpose: JSON persistence and loading with safety guarantees
- Location: `src/chaoscatcher/storage.py`
- Contains: load_json(), save_json() (atomic writes, corruption guards)
- Depends on: None (pure file I/O)
- Used by: Application logic via Store class

**Infrastructure/Utilities:**
- Purpose: Cross-cutting concerns and support functions
- Location: `src/chaoscatcher/paths.py` (path resolution), `src/chaoscatcher/timeparse.py` (time parsing), `src/chaoscatcher/_util.py` (datetime helpers), `src/chaoscatcher/safety.py` (git repo guards), `src/chaoscatcher/notification_popup.py` (desktop notifications)
- Contains: Time parsing, path resolution, safety checks, audio/visual alerts
- Depends on: None (single-responsibility)
- Used by: All other layers

## Data Flow

**Entry Creation (Medication/Mood/Fuel):**

1. User submits form (GUI dialog or CLI args)
2. Input validated via timeparse.parse_ts() and field checks
3. Entry record created as dict: `{"ts": "2026-03-16T14:30:00-05:00", "name": "Vyvanse", ...}`
4. Store.load() retrieves current data (auto-initializes missing keys)
5. Entry appended to type-specific list (medications, moods, water, fuel, etc.)
6. Store.save() writes updated dict to JSON file atomically
7. UI list refreshed to show new entry

**Nudge Evaluation Loop (every 60 seconds):**

1. QTimer._tick_minute() fires in ChaosCatcherApp
2. App loads today's water + fuel entries from store
3. compute_fuel_stats() calculates hydration/nutrition metrics for today
4. evaluate_nudges() checks config rules:
   - Protein deadline (14:00 default, blocks if not logged)
   - Food gap (max 6 hours, blocks if exceeded)
   - Water milestones (16 oz by 12:00, 32 oz by 15:00, etc.)
   - Water gap (3+ hours idle)
5. If severity == "yellow": NotificationPopup shown + sound played
6. If severity == "gray": silently snooze (cooldown or quiet hours)
7. If severity == "green": no action

**Stats Calculation (on-demand):**

1. App retrieves type-specific entries from store (medications, moods, sleep)
2. Filter by date range (last N days)
3. Aggregate: counts, averages, min/max, trends
4. For mood: compute daily averages and Pearson correlation vs sleep/water
5. Render as text report (Stats tab) or CSV export

**State Management:**

- All persistent state lives in single JSON file at `~/.config/chaoscatcher/data.json`
- Keys: medications, moods, water, fuel, focus_sessions, daily_logs, fuel_config, daily_med_list, water_goal_oz
- Transient state (UI state, timers, popups) stored in ChaosCatcherApp instance

## Key Abstractions

**Entry (Record) Model:**

Untyped dict with flexible shape:

```json
{
  "ts": "2026-03-16T14:30:00-05:00",
  "name": "Vyvanse",
  "dose": "50 mg",
  "notes": "taken with food"
}
```

- All entries have timestamp (ISO 8601 with local tz)
- Type determined by which list it appears in (medications, moods, water, fuel, etc.)
- Purpose: Polymorphic record model lets CLI and GUI handle varied data types with minimal duplication

**Store:**

Singleton abstraction over JSON file:

```python
class Store:
    def load(self) -> dict[str, Any]
    def save(self, data: dict[str, Any]) -> None
```

- Location: `src/chaoscatcher/gui.py` (nested in gui.py, not storage.py)
- Purpose: Provides single entry point to load/save data with defaults
- Encapsulates data path resolution

**FuelConfig + FuelStats:**

Pure dataclasses for hydration/nutrition logic:

```python
@dataclass
class FuelConfig:
    fuel_enabled: bool
    quiet_hours_start: str
    nudge_cooldown_min: int
    ...

@dataclass
class FuelStats:
    water_oz_today: float
    last_food_ts: Optional[datetime]
    hours_since_food: Optional[float]
    ...
```

- Purpose: Decouple nudge engine from storage/UI
- All functions in fuel_engine.py are pure (no side effects)
- Config serializable to/from dict for JSON persistence

**Vyvanse Arc Phase Colors:**

```python
VY_PHASE_COLORS = {
    "Not yet": "#6b7280",
    "Loading": "#94a3b8",
    "Onset": "#60a5fa",
    "Peak": "#22c55e",
    ...
}
```

- Purpose: Visual feedback for medication phase tracking
- Calculated from medication timestamps relative to dose time
- Rendered as colored bar at top of window (phase_bar)

## Entry Points

**CLI (`chaos` command):**
- Location: `src/chaoscatcher/cli.py:main()`
- Triggers: User runs `chaos med add ...` or `chaos mood list`
- Responsibilities:
  - Parse arguments via argparse
  - Route to cmd_* functions (cmd_med_add, cmd_mood_list, etc.)
  - Read/write data via Store
  - Format output for terminal (line blocks, CSV, sparklines, tables)

**GUI (`ccgui` command):**
- Location: `src/chaoscatcher/gui.py:run_gui()`
- Triggers: User runs `ccgui`
- Responsibilities:
  - Instantiate PySide6 QApplication
  - Create ChaosCatcherApp (QMainWindow)
  - Build 7 tabs (Medication, Mood, Sleep, Fuel, Stats, Export, Focus)
  - Start event loop with minute-based timer for nudge eval
  - Handle user interactions (forms, buttons, timers)
  - Render charts (mood graph with trend analysis)

**Entry point definitions in pyproject.toml:**
```
[project.scripts]
chaos = "chaoscatcher.cli:main"
ccgui = "chaoscatcher.gui:run_gui"
```

## Error Handling

**Strategy:** Defensive with silent fallbacks + user-facing alerts.

**Patterns:**

1. **Data corruption:** storage.py's load_json() backs up corrupt files and resets to `{}`
2. **Time parsing:** timeparse.parse_ts() raises SystemExit with helpful message on bad input
3. **UI errors:** ChaosCatcherApp._safe_call() catches exceptions, shows QMessageBox, logs traceback
4. **File permissions:** storage.py attempts chmod 0o600 (best-effort) on save
5. **Missing git repo:** safety.py raises SystemExit if data file lives inside .git (unless --allow-repo-data-path)

## Cross-Cutting Concerns

**Logging:** No structured logging. Uses print() to stdout/stderr for CLI, QMessageBox for GUI errors.

**Validation:** Time parsing (timeparse.py) validates input formats. Score validation (1–10 for moods) is implicit via argparse type checking and field validation in dialogs.

**Authentication:** None. Local-only, single-user tool.

**Timezone Handling:** All timestamps are ISO 8601 with local timezone. _util.py._now_local() and _dt_from_entry_ts() handle conversions.

**Notifications:**
- Desktop: NotificationPopup (Qt top-level window, top-right corner, fade-out after 5s)
- Audio: nudge.wav asset played via QSoundEffect
- Quiet hours: 22:00–09:00 (configurable in FuelConfig)

---

*Architecture analysis: 2026-03-16*
