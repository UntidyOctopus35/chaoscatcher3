# Codebase Structure

**Analysis Date:** 2026-03-16

## Directory Layout

```
chaoscatcher3/
├── .github/              # CI/CD configuration (GitHub Actions)
├── .planning/            # GSD planning documents
│   └── codebase/         # Architecture/structure reference docs (this file)
├── assets/               # Audio files (nudge.wav), icons
├── src/
│   └── chaoscatcher/     # Main package
│       ├── __init__.py       # Version info
│       ├── __pycache__/      # Compiled Python cache
│       ├── _util.py          # Shared datetime utilities
│       ├── cli.py            # CLI entry point + command handlers
│       ├── fuel_engine.py     # Nudge logic (pure functions)
│       ├── gui.py            # GUI entry point + PySide6 app
│       ├── notification_popup.py  # Desktop notification widget
│       ├── paths.py          # Data path resolution
│       ├── safety.py         # Git repo safety checks
│       ├── storage.py        # JSON load/save with corruption guards
│       ├── timeparse.py      # Flexible time parsing
│       └── chaoscatcher.egg-info/  # Package metadata
├── tests/
│   ├── __init__.py
│   ├── __pycache__/
│   ├── test_cli_helpers.py     # Tests for time/formatting helpers
│   ├── test_gui_helpers.py     # Tests for GUI utility functions
│   ├── test_storage.py         # Tests for JSON load/save
│   └── test_timeparse.py       # Tests for time parsing
├── .gitignore
├── .pre-commit-config.yaml
├── .pytest_cache/
├── .ruff_cache/
├── LICENSE
├── README.md
├── pyproject.toml          # Package metadata, entry points, tool config
└── .venv/                  # Virtual environment (not committed)
```

## Directory Purposes

**`src/chaoscatcher/`:**
- Purpose: Main application package
- Contains: Core logic, UI, storage, utilities
- Key files: `cli.py` (CLI), `gui.py` (GUI), `fuel_engine.py` (nudge logic), `storage.py` (persistence)

**`tests/`:**
- Purpose: Unit test suite
- Contains: Pytest test files
- Key files: `test_storage.py`, `test_timeparse.py`, `test_cli_helpers.py`, `test_gui_helpers.py`

**`assets/`:**
- Purpose: Static resources (audio)
- Contains: `nudge.wav` (chime sound for notifications)

**`.planning/`:**
- Purpose: GSD planning and analysis documents
- Contains: Architecture reference, task plans, phase summaries

## Key File Locations

**Entry Points:**
- `src/chaoscatcher/cli.py:main()` — CLI entry point (registered as `chaos` command)
- `src/chaoscatcher/gui.py:run_gui()` — GUI entry point (registered as `ccgui` command)

**Core Application Logic:**
- `src/chaoscatcher/gui.py` — PySide6 main window, 7 tabs, event loop (3184 lines)
- `src/chaoscatcher/cli.py` — Subcommand handlers (med, mood, sleep, fuel, focus), stats, export (1083 lines)

**Data Persistence:**
- `src/chaoscatcher/storage.py` — load_json(), save_json() with atomic writes and corruption recovery
- `src/chaoscatcher/gui.py:Store` class — Encapsulates data path + load/save operations

**Domain Logic:**
- `src/chaoscatcher/fuel_engine.py` — FuelConfig, FuelStats, compute_fuel_stats(), evaluate_nudges() (pure functions)
- `src/chaoscatcher/notification_popup.py` — NotificationPopup widget, audio playback

**Utilities:**
- `src/chaoscatcher/timeparse.py` — Flexible user time parsing (ISO, human, relative, keywords)
- `src/chaoscatcher/_util.py` — Shared datetime helpers (_now_local, _fmt_time, _dt_from_entry_ts)
- `src/chaoscatcher/paths.py` — Data path resolution (env var, CLI arg, default)
- `src/chaoscatcher/safety.py` — Git repo safety checks (prevent storing health data in repos)

**Configuration:**
- `pyproject.toml` — Package name, version, dependencies, entry points, tool config (ruff, pytest)

## Naming Conventions

**Files:**
- Lowercase with underscores: `fuel_engine.py`, `notification_popup.py`
- Test files: `test_{module}.py` (e.g., `test_storage.py`)
- Package: `chaoscatcher` (single word, lowercase)

**Directories:**
- Lowercase with underscores: `__pycache__`, `egg-info`
- Top-level: CamelCase or lowercase (`src`, `tests`, `assets`)

**Functions:**
- Private (module-only): `_function_name()` (leading underscore)
- Public: `function_name()`
- Helpers: Descriptive names like `_parse_ts()`, `_ensure_parent()`, `_sparkline()`

**Classes:**
- PascalCase: `Store`, `ChaosCatcherApp`, `NotificationPopup`, `StatsReportDialog`, `MoodGraphWidget`
- Dataclasses: `FuelConfig`, `FuelStats`, `NudgeResult`

**Variables:**
- Local/module: `lowercase_with_underscores`
- Constants: `UPPERCASE_WITH_UNDERSCORES` (e.g., `VY_PHASE_COLORS`)
- Internal state: Leading underscore (e.g., `self._focus_running`)

**Type Annotations:**
- Python 3.10+: `from __future__ import annotations`, use str | None instead of Optional[str]
- All functions use type hints for params and return values

## Where to Add New Code

**New Feature (e.g., Sleep tracking improvements):**
- Primary code: `src/chaoscatcher/gui.py` (add tab builder like `_build_sleep_tab()`, refresh method `_refresh_sleep_list()`)
  - Also add CLI commands in `src/chaoscatcher/cli.py` (cmd_sleep_add, cmd_sleep_list, etc.)
- Tests: `tests/test_gui_helpers.py` (GUI-related) or `tests/test_cli_helpers.py` (CLI-related)
- Data model: Extend Store.load() defaults in `src/chaoscatcher/gui.py` (add key to data dict)
- Persistence: Use existing Store.load()/save() — no new storage code needed

**New Pure Logic Module (e.g., Sleep phase detection):**
- Implementation: Create `src/chaoscatcher/sleep_phase.py` (similar to `fuel_engine.py`)
- Pattern: Use dataclasses for input/output, all functions pure (no side effects)
- Tests: Create `tests/test_sleep_phase.py`
- Integration: Import in `src/chaoscatcher/gui.py` and `src/chaoscatcher/cli.py` as needed

**Utility Helper:**
- Shared (CLI + GUI): Add to `src/chaoscatcher/_util.py` (time, formatting)
- CLI-only: Keep inside `src/chaoscatcher/cli.py` (avoid polluting exports)
- GUI-only: Keep inside `src/chaoscatcher/gui.py` (keep module focused)

**New Notification Type:**
- Add to `src/chaoscatcher/notification_popup.py` or extend existing NotificationPopup
- Test integration in `tests/test_gui_helpers.py`

## Special Directories

**`.venv/`:**
- Purpose: Python virtual environment
- Generated: Yes
- Committed: No (in .gitignore)
- Contents: Python interpreter, pip, dependencies (setuptools, pytest, ruff, matplotlib, PySide6)

**`__pycache__/`:**
- Purpose: Python bytecode cache
- Generated: Yes (by Python)
- Committed: No (in .gitignore)

**`.pytest_cache/`:**
- Purpose: Pytest fixture/test discovery cache
- Generated: Yes (by pytest)
- Committed: No (in .gitignore)

**`.ruff_cache/`:**
- Purpose: Ruff linter cache
- Generated: Yes (by ruff)
- Committed: No (in .gitignore)

**`chaoscatcher.egg-info/`:**
- Purpose: Setuptools package metadata
- Generated: Yes (by pip install -e)
- Committed: No (in .gitignore)

## Import Structure

**Public APIs (intended to be imported):**

```python
from chaoscatcher.storage import load_json, save_json
from chaoscatcher.paths import resolve_data_path, default_data_path
from chaoscatcher.timeparse import parse_ts
from chaoscatcher.fuel_engine import FuelConfig, FuelStats, compute_fuel_stats, evaluate_nudges
from chaoscatcher.notification_popup import NotificationPopup
```

**Internal modules (used within package, not re-exported):**

```python
from ._util import _now_local, _fmt_time, _dt_from_entry_ts
from .safety import assert_safe_data_path
```

**CLI and GUI are entry points, not imported elsewhere.**

---

*Structure analysis: 2026-03-16*
