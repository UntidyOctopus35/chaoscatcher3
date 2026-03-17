# Architecture Research

**Domain:** PySide6 desktop health-tracking app refactor
**Researched:** 2026-03-16
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Presentation Layer                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ MedsView │  │ MoodView │  │ FuelView │  │ RegView  │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │              │              │              │          │
│  ┌────┴──────────────┴──────────────┴──────────────┴─────┐   │
│  │                   MainWindow                           │   │
│  │            (tab wiring, theme, timers)                  │   │
│  └────────────────────────┬───────────────────────────────┘   │
├───────────────────────────┼───────────────────────────────────┤
│                     Domain Layer                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │ fuel_engine   │  │nervous_system│  │ interpretation   │    │
│  │ (nudges)      │  │ (detection)  │  │ (humane alerts)  │    │
│  └──────────────┘  └──────────────┘  └──────────────────┘    │
├───────────────────────────────────────────────────────────────┤
│                     Data Layer                                │
│  ┌──────────────┐  ┌──────────────┐                          │
│  │   storage.py  │  │   models.py  │                          │
│  │  (JSON I/O)   │  │ (data types) │                          │
│  └──────────────┘  └──────────────┘                          │
└───────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation |
|-----------|----------------|----------------|
| MainWindow | Tab wiring, theme application, timer loops, fuel banner | `gui.py` → thin shell after refactor |
| Views (per tab) | UI rendering, user input, list display for one tracking type | `views/meds_view.py`, `views/mood_view.py`, etc. |
| Dialogs | Modal entry forms for adding/editing records | `dialogs/med_dialog.py`, `dialogs/mood_dialog.py`, etc. |
| Widgets | Reusable UI components (mood graph, arc bar, timeline) | `widgets/mood_graph.py`, `widgets/arc_bar.py`, etc. |
| Domain engines | Pure-function business logic (no Qt, no I/O) | `fuel_engine.py`, `nervous_system.py`, `interpretation.py` |
| Storage | JSON file I/O with atomic writes and corruption recovery | `storage.py` (keep as-is) |
| Models | Data type definitions and constants | New `models.py` — entry types, colors, config dataclasses |

## Recommended Project Structure

```
src/chaoscatcher/
├── __init__.py
├── main_window.py          # Thin MainWindow shell (was gui.py)
├── models.py               # NEW: Entry types, colors, constants
├── theme.py                # NEW: Centralized QSS theme + color constants
├── views/                  # NEW: One module per tab
│   ├── __init__.py
│   ├── meds_view.py        # Medication tab
│   ├── mood_view.py        # Mood tab
│   ├── sleep_view.py       # Sleep tab
│   ├── fuel_view.py        # Fuel tab
│   ├── focus_view.py       # Focus tab
│   ├── stats_view.py       # Stats tab
│   ├── export_view.py      # Export tab
│   └── regulation_view.py  # NEW: Regulation tab
├── dialogs/                # NEW: Entry dialogs
│   ├── __init__.py
│   ├── med_dialog.py
│   ├── mood_dialog.py
│   ├── sleep_dialog.py
│   └── fuel_dialog.py
├── widgets/                # NEW: Reusable components
│   ├── __init__.py
│   ├── mood_graph.py       # Extracted from gui.py MoodGraphWidget
│   ├── arc_bar.py          # Vyvanse arc visualization
│   └── entry_list.py       # Common entry list pattern
├── nervous_system.py       # NEW: Detection engine (from CCP)
├── interpretation.py       # NEW: Humane alert generation (from CCP)
├── fuel_engine.py          # Keep as-is
├── storage.py              # Keep as-is
├── notification_popup.py   # Keep as-is
├── safety.py               # Keep as-is
├── cli.py                  # Keep as-is
├── paths.py                # Keep as-is
├── timeparse.py            # Keep as-is
└── _util.py                # Keep as-is
```

### Structure Rationale

- **views/:** Each tab is a self-contained QWidget subclass. MainWindow just adds them to QTabWidget. This mirrors CCP's proven structure.
- **dialogs/:** Entry forms are modal and reusable. Separating them makes each testable and prevents view bloat.
- **widgets/:** Shared components (mood graph, arc bar) are used across multiple views. Extracting prevents duplication.
- **models.py:** Centralized type definitions prevent magic strings scattered across files. Entry types, color maps, and config dataclasses.
- **theme.py:** One file for all styling — easy to modify, consistent across views.

## Architectural Patterns

### Pattern 1: View Protocol

**What:** Each view module exports a QWidget subclass that takes a Store reference and provides a `refresh()` method.
**When to use:** Every tab in the application.
**Trade-offs:** Slightly more boilerplate per view, but each view is independently testable and modifiable.

**Example:**
```python
class MedsView(QWidget):
    def __init__(self, store: Store, parent=None):
        super().__init__(parent)
        self.store = store
        self._build_ui()

    def _build_ui(self):
        # All UI construction here
        ...

    def refresh(self):
        # Reload data from store and update display
        ...
```

### Pattern 2: Pure Domain Functions

**What:** Business logic functions take data in, return results out. No Qt imports, no I/O.
**When to use:** Fuel engine, nervous system detection, interpretation.
**Trade-offs:** Requires adapter layer between Qt views and domain functions.

**Example:**
```python
# nervous_system.py — pure functions
def compute_nervous_system_load(entries: list[dict]) -> LoadScore:
    ...

# views/regulation_view.py — Qt adapter
def _refresh_load(self):
    entries = self.store.load().get("moods", [])
    load = compute_nervous_system_load(entries)
    self._render_load(load)
```

### Pattern 3: Centralized Theme

**What:** All colors, fonts, and spacing defined in one module. Views reference constants, not hardcoded values.
**When to use:** Every widget and view.
**Trade-offs:** Initial effort to extract all hardcoded styles, but one-time cost.

**Example:**
```python
# theme.py
BG_PRIMARY = "#1E293B"
BG_SURFACE = "#334155"
TEXT_PRIMARY = "#F8FAFC"
ACCENT_MED = "#4A90D9"
ACCENT_MOOD = "#A855F7"

def apply_theme(app: QApplication):
    app.setStyleSheet(f"""
        QMainWindow {{ background: {BG_PRIMARY}; }}
        QLabel {{ color: {TEXT_PRIMARY}; }}
        ...
    """)
```

## Data Flow

### Entry Logging Flow

```
[User fills dialog form]
    ↓
[Dialog validates input]
    ↓
[Dialog returns entry dict]
    ↓
[View appends to Store data]
    ↓
[Store.save() → atomic JSON write]
    ↓
[View.refresh() → re-reads Store, updates UI]
```

### Regulation Detection Flow

```
[Timer tick or tab switch]
    ↓
[RegulationView.refresh()]
    ↓
[Store.load() → get all entries]
    ↓
[nervous_system.py functions → detect patterns]
    ↓
[interpretation.py → wrap in humane language]
    ↓
[RegulationView renders alerts, load score, dip type]
```

### Key Data Flows

1. **Entry creation:** Dialog → Store.save() → View.refresh() — simple write-then-read cycle
2. **Regulation analysis:** Store.load() → detection functions → interpretation → UI render — read-only analysis pipeline
3. **Fuel nudges:** Timer → fuel_engine.evaluate_nudges() → banner update — periodic pure-function evaluation

## Build Order (Refactor Sequence)

The refactor must preserve working functionality at every step. Suggested order:

1. **Extract models.py** — entry types, color constants (low risk, no UI changes)
2. **Extract theme.py** — centralize all QSS (visual change, but mechanical extraction)
3. **Extract widgets/** — MoodGraphWidget, arc bar (self-contained, easy to test)
4. **Extract views/** one at a time — start with simplest (Export), end with most complex (Stats/Mood)
5. **Slim gui.py → main_window.py** — what remains is just tab wiring
6. **Add nervous_system.py + interpretation.py** — pure Python, no refactor risk
7. **Add RegulationView** — clean addition to modular structure

## Anti-Patterns

### Anti-Pattern 1: Big Bang Refactor

**What people do:** Rewrite gui.py from scratch in one pass.
**Why it's wrong:** Introduces regressions across all tabs simultaneously. Impossible to test incrementally.
**Do this instead:** Extract one view at a time. Each extraction is a working commit. Run tests after each.

### Anti-Pattern 2: View Knows About Other Views

**What people do:** MedsView directly calls MoodView.refresh() when a medication is logged.
**Why it's wrong:** Creates circular dependencies, makes views untestable in isolation.
**Do this instead:** Views emit signals. MainWindow connects signals to refresh other views.

### Anti-Pattern 3: Business Logic in Views

**What people do:** Mood baseline calculations, sleep analysis, etc. inside view code.
**Why it's wrong:** Can't test without Qt, can't reuse in CLI, bloats view files.
**Do this instead:** Pure functions in domain modules. Views call functions and render results.

## Sources

- CCPrivate codebase — successfully refactored from similar monolith to views/dialogs/widgets structure
- PySide6 documentation — signal/slot patterns, QSS styling reference
- CC3 codebase mapping — current architecture, structure, and concerns analysis

---
*Architecture research for: PySide6 health/regulation tracking desktop app refactor*
*Researched: 2026-03-16*
