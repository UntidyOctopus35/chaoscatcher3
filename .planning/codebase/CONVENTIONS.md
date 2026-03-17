# Coding Conventions

**Analysis Date:** 2026-03-16

## Naming Patterns

**Files:**
- Snake case: `storage.py`, `timeparse.py`, `notification_popup.py`
- Module files use lowercase with underscores
- Entry point files: `cli.py`, `gui.py`, `__init__.py`

**Functions:**
- Snake case: `_now_local()`, `load_json()`, `compute_fuel_stats()`, `evaluate_nudges()`
- Private/helper functions prefixed with `_`: `_parse_time()`, `_in_quiet_hours()`, `_ensure_parent()`
- Function names are descriptive verbs: `parse_*`, `load_*`, `save_*`, `evaluate_*`, `compute_*`

**Variables:**
- Snake case: `water_oz_today`, `hours_since_food`, `nudge_cooldown_min`, `quiet_hours_start`
- Config parameters use descriptive names: `food_max_gap_hours`, `protein_deadline_time`
- Single-letter loop variables acceptable in small scopes: `h`, `m`, `x`, `y`, `v`

**Types:**
- Dataclass names are PascalCase: `FuelConfig`, `FuelStats`, `NudgeResult`
- Type hints use modern Python typing: `dict[str, Any]`, `list[dict]`, `Optional[datetime]`, `datetime | None`
- Dict keys are lowercase strings: `"ts"`, `"oz"`, `"protein"`, `"carb"`

## Code Style

**Formatting:**
- Line length: 120 characters (configured in `pyproject.toml`)
- 4-space indentation
- Double quotes for strings (configured in `pyproject.toml`)
- `from __future__ import annotations` at top of all modules for forward references

**Linting:**
- Tool: `ruff` (v0.15)
- Selected rules: E (errors), F (pyflakes), W (warnings), I (import sorting)
- Config file: `pyproject.toml` sections `[tool.ruff]` and `[tool.ruff.lint]`
- Auto-formatters: `ruff check --fix` and `ruff format`
- Pre-commit hooks configured to auto-fix: `.pre-commit-config.yaml`

**Import organization:**
- Standard library first: `import json`, `import os`, `from pathlib import Path`
- Then third-party: `import pytest`, `from PySide6.QtCore import Qt`
- Then local/internal: `from .storage import load_json, save_json`
- Import sorting handled by ruff with `I` rule

**Path Aliases:**
- No aliases configured
- Relative imports used: `from ._util import _now_local`
- Absolute imports from package: `from chaoscatcher.storage import load_json`

## Error Handling

**Patterns:**

1. **Exceptions as control flow** (timeparse):
```python
try:
    dt = datetime.fromisoformat(value.strip())
    return dt.isoformat(timespec="seconds")
except ValueError:
    pass  # Continue trying next format
```

2. **Graceful fallback with SystemExit** (cli/gui):
```python
raise SystemExit(
    "Could not parse time {value!r}. Try ISO like '2026-02-25T07:34:00-05:00'..."
)
```

3. **Silent handling with defaults** (storage):
```python
try:
    data = json.loads(txt)
    return data if isinstance(data, dict) else {}
except json.JSONDecodeError:
    # corruption guard: backup then reset
    backup = path.with_suffix(f".corrupt-{int(time.time())}.json")
    backup.write_text(txt, encoding="utf-8")
    save_json(path, {})
    return {}
```

4. **Broad exception catching with pass** (_util):
```python
def _dt_from_entry_ts(ts: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_now_local().tzinfo)
        return dt.astimezone()
    except Exception:
        return None
```

**Error handling philosophy:**
- Validate input early with specific checks
- Return None or empty defaults rather than raising exceptions where possible
- Use SystemExit for CLI argument parsing errors
- Backup corrupted data before resetting (storage.py)
- Wrap third-party exceptions in custom messages for user-facing contexts

## Logging

**Framework:** `print()` with optional `file=sys.stderr` for errors

**Patterns:**
```python
# Error output (safety.py):
print("🚫 Refusing to use a data file inside a git repo.", file=sys.stderr)
print(f"   data_path: {data_path}", file=sys.stderr)
```

**When to log:**
- Safety/security warnings: print to stderr with emoji
- Internal debug: use print() with informative messages
- Entry operations: handled by calling code, not inside storage/parsing

## Comments

**When to comment:**
- Complex logic: e.g., `# Wraps midnight (e.g. 22:00 -> 09:00)` in `fuel_engine.py` line 160
- Regex patterns: explain what pattern matches
- Workarounds: e.g., `# Windows-safe formatting` in `_util.py` for strftime variations
- State machine logic: document state transitions
- Non-obvious calculations: explain intent

**Docstring/JSDoc pattern:**
- Module-level docstrings: Describe purpose and responsibility
```python
"""
Fuel & Hydration nudge engine — pure functions.

Evaluates four conditions:
  1. Protein deadline (no protein logged by a configurable time)
  2. Food gap (too long since last food entry)
  3. Water minimum by time (behind on water milestones)
  4. Water gap (too long since last water entry)

All user-facing strings follow tone rules:
  Never: "failed", "should", "overdue", "calories"
  Use: "check", "might help", "quick", "support"
"""
```

- Function docstrings: One-line summary plus details for complex functions
```python
def load_json(path: Path) -> dict[str, Any]:
    """
    Safe load:
    - creates parent dirs
    - if missing/empty -> writes {}
    - if corrupt -> backs up raw text then resets to {}
    Always returns a dict.
    """
```

- Parameter documentation inline in docstring, not @param style

## Function Design

**Size:**
- Helper functions: 5–30 lines typical
- Complex logic broken into private helpers: `_parse_time()`, `_in_quiet_hours()`, `_ensure_parent()`
- Dataclass methods small: `to_dict()`, `from_dict()` are 8–15 lines each

**Parameters:**
- Explicit parameters over config dicts where possible
- Optional parameters use `None` defaults: `now: Optional[datetime] = None`
- Config objects (dataclasses) passed whole: `config: FuelConfig`
- No *args/**kwargs in public functions

**Return values:**
- Simple types preferred: `str`, `bool`, `int`, `float`, `list`, `dict`, `Path`
- None for "not found": `Optional[datetime]`, `datetime | None`
- Dataclass results for complex returns: `NudgeResult`, `FuelStats`
- Always return same type (no implicit None; use dataclass defaults instead)

## Module Design

**Exports:**
- No `__all__` lists; module structure implicit from function naming
- Private functions prefixed with `_` are internal
- Public functions/classes have no prefix
- Modules are focused: `storage.py` has JSON I/O only; `fuel_engine.py` has nudge logic only

**Barrel files:**
- No barrel files (no index re-exports)
- Direct imports from target modules: `from .storage import load_json, save_json`

**Module organization pattern:**
1. Module docstring (if complex logic)
2. Imports (stdlib, third-party, local)
3. Helper/private functions (prefixed `_`)
4. Dataclasses/config classes
5. Public functions
6. Classes (if any)

**Example**: `fuel_engine.py` has:
- Module docstring
- Imports
- `FuelConfig` and `FuelStats` dataclasses
- `NudgeResult` dataclass
- Private helpers: `_parse_time()`, `_in_quiet_hours()`
- Public function: `compute_fuel_stats()`, `evaluate_nudges()`

## Type Hints

**Pattern:**
- All function signatures include type hints
- Return types always specified
- Generic types: `list[dict]`, `dict[str, Any]` (not `List`, `Dict` from typing)
- Optional: `Optional[type]` or `type | None` (modern style preferred)
- String types used where circular imports would occur (with `from __future__ import annotations`)

**Example:**
```python
def compute_fuel_stats(
    water_entries: list[dict],
    fuel_entries: list[dict],
    now: Optional[datetime] = None,
) -> FuelStats:
```

## Tone & Voice (User-Facing Strings)

Applies to nudge messages and UI labels:

**Never use:**
- "failed", "overdue", "should", "calories", "missed"

**Do use:**
- "check", "might help", "quick", "support", "little"

**Example patterns:**
```python
result.messages.append("Fuel check: no protein logged yet today.")
result.messages.append("Hydration check: a little water now may help.")
result.suggested_actions.append("+8 oz")
```

---

*Convention analysis: 2026-03-16*
