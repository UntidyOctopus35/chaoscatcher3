# Stack Research

**Domain:** Personal health/regulation tracking desktop app (PySide6 refactor + polish)
**Researched:** 2026-03-16
**Confidence:** HIGH

## Recommended Stack

### Core Technologies (Already In Use — Keep)

| Technology | Version | Purpose | Why Keep |
|------------|---------|---------|----------|
| Python | 3.10+ (currently 3.12) | Application runtime | Stable, well-supported, user's primary language |
| PySide6 | 6.10.x | Desktop GUI framework | Already in use, Qt is the best choice for cross-platform desktop |
| matplotlib | 3.10.x | Charts and data viz | Already integrated, QtAgg backend works well |
| JSON (stdlib) | — | Data storage | Simple, no dependencies, backwards compatible |

### Supporting Libraries (Add for This Milestone)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| qt-material | 2.14+ | Material Design theme for Qt | Apply as base dark theme, customize on top — gives professional look with minimal effort |
| (none needed) | — | Nervous system engine | Port from CCP — pure Python, no new deps |

### Development Tools (Already In Use — Keep)

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest | Testing | Already configured in pyproject.toml |
| ruff | Linting + formatting | Already configured as pre-commit hook |
| pre-commit | Git hooks | Already set up |

## Installation

```bash
# Add for theming (optional — can also do pure QSS)
pip install qt-material

# No other new dependencies needed
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| qt-material for base theme | Pure QSS stylesheet | If qt-material adds too much weight or doesn't match the regulation-centered aesthetic — pure QSS gives full control |
| matplotlib for charts | pyqtgraph | If real-time charting becomes needed (pyqtgraph is faster for live data) — matplotlib is fine for static daily summaries |
| JSON flat-file storage | SQLite | If query complexity grows significantly — but current dict-based access pattern works fine |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| PyQt6 | GPL license incompatible with permissive OSS, API nearly identical to PySide6 | PySide6 (LGPL) |
| QML/Qt Quick | Massive complexity increase, different paradigm, not needed for this app | PySide6 Widgets |
| SQLAlchemy / heavy ORMs | Overkill for single-user JSON flat-file storage, adds dependency weight | Keep JSON + storage.py |
| Electron/web frameworks | Defeats the purpose of lightweight local-first desktop app | PySide6 |
| qt-material themes that are "light" | Violates dark-mode-always constraint and regulation-centered design | Dark variant only |

## Stack Patterns

**For the visual polish phase:**
- Use centralized QSS stylesheet file (e.g., `src/chaoscatcher/theme.py` or `theme.qss`)
- Define color constants in one place, reference everywhere
- Follow CCP's proven color palette: slate backgrounds (#1E293B), light text (#F8FAFC), category-specific accent colors

**For the refactor phase:**
- Extract tab builders into `views/` modules (one per tab)
- Extract dialogs into `dialogs/` modules
- Extract reusable widgets into `widgets/`
- Keep `gui.py` as thin MainWindow shell that wires tabs together

**For the nervous system engine:**
- Pure Python modules (no Qt dependency) — `nervous_system.py` + `interpretation.py`
- Thin adapter to convert CC3's dict data to the detection functions' expected format
- View module (`views/regulation_view.py`) handles all Qt rendering of alerts

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| PySide6 6.10.x | Python 3.10-3.12 | Stable on all supported Python versions |
| matplotlib 3.10.x | PySide6 6.10.x | QtAgg backend confirmed working |
| qt-material 2.14+ | PySide6 6.x | Supports PySide6 natively |

## Sources

- CCP (CCPrivate) codebase — proven architecture patterns and theme approach
- PySide6 official documentation — widget styling, QSS reference
- Existing CC3 codebase analysis — current state understood via codebase mapping

---
*Stack research for: PySide6 health/regulation tracking desktop app*
*Researched: 2026-03-16*
