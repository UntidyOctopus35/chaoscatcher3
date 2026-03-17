# Technology Stack

**Analysis Date:** 2026-03-16

## Languages

**Primary:**
- Python 3.12 - All application logic, CLI, and GUI

## Runtime

**Environment:**
- Python 3.10+ required (minimum specified in `pyproject.toml`)
- Currently running on Python 3.12.3
- Virtual environment: `.venv/`

**Package Manager:**
- pip (standard Python package manager)
- Lockfile: Not present (relies on `pyproject.toml` for reproducibility)

## Frameworks

**GUI:**
- PySide6 6.10.2 - Desktop GUI framework (Qt bindings for Python)
- Matplotlib 3.10.8 - Charting and data visualization
- Matplotlib backend: `QtAgg` for Qt integration (set in `src/chaoscatcher/gui.py`)

**CLI:**
- Argparse (standard library) - Command-line interface argument parsing

**Data Handling:**
- CSV (standard library) - CSV export/import for data
- JSON (standard library) - All data storage (flat-file JSON database)

**Testing:**
- pytest 8.0+ (dev dependency) - Test runner
- Config: `pyproject.toml` → `testpaths = ["tests"]`

**Code Quality:**
- ruff 0.15+ (dev dependency) - Linting and code formatting
- pre-commit 4.0+ (dev dependency) - Git hooks for code quality

## Key Dependencies

**Critical:**
- PySide6 6.10.2 - Desktop GUI framework; core to application interface
- Matplotlib 3.8+ - Charts and visualizations (required in base dependencies)
- NumPy 2.4.2 - Numerical operations (matplotlib dependency)

**Secondary (via PySide6/Matplotlib):**
- Pillow 12.1.1 - Image processing (matplotlib dependency)
- PyYAML - Configuration (if used via dependencies)
- python-dateutil 2.9.0 - Date/time parsing utilities

**Development Tools (extras):**
- pytest 8.0+ - Testing framework
- ruff 0.15+ - Linting and formatting
- pre-commit 4.0+ - Git hooks automation

## Configuration

**Environment:**
- Data file location: `~/.config/chaoscatcher/data.json` (default)
- Override via:
  - Environment variable: `CHAOSCATCHER_DATA` → path to JSON file
  - Command-line flag: `--data ~/my-data.json`
  - Profile flag: `--profile work` → `~/.config/chaoscatcher/work.json`
- See `src/chaoscatcher/paths.py` for path resolution logic

**Build:**
- Build system: setuptools 68+, wheel
- Entry points defined in `pyproject.toml`:
  - `chaos` → `chaoscatcher.cli:main` (CLI command)
  - `ccgui` → `chaoscatcher.gui:run_gui` (GUI launcher)
- Installation: `pip install -e ".[dev]"` (editable install with dev deps)

**Code Style:**
- Line length: 120 characters
- Quote style: double quotes
- Indent: spaces (standard 4)
- Ruff lint rules: E (errors), F (pyflakes), W (warnings), I (isort imports)
- Pre-commit hooks: Auto-fix with `ruff check --fix` and `ruff format`

## Platform Requirements

**Development:**
- Python 3.10+
- Linux/macOS/Windows (WSL2 supported — project designed for WSL2)
- GUI requires X11 or display server (WSLg on WSL2, native on Linux/macOS)
- tkinter NOT required (uses PySide6 instead)

**Production:**
- Python 3.10+ runtime
- Display server for GUI mode (headless CLI runs without GUI)
- Local file system access (reads/writes to `~/.config/chaoscatcher/`)
- Permissions: Data file created with mode 0600 (owner read/write only)

---

*Stack analysis: 2026-03-16*
