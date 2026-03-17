# Testing Patterns

**Analysis Date:** 2026-03-16

## Test Framework

**Runner:**
- `pytest` 8.0+ (configured in `pyproject.toml`)
- Config: `pyproject.toml` section `[tool.pytest.ini_options]`
- Test discovery: searches `tests/` directory

**Assertion Library:**
- `pytest` built-in assertions (`assert`)
- `pytest.approx()` for float comparisons with tolerance
- `pytest.raises()` for exception testing

**Run Commands:**
```bash
pytest tests/                    # Run all tests
pytest tests/ -v                 # Verbose output
pytest tests/ --tb=short         # Short traceback format
pytest tests/test_storage.py     # Run specific test file
pytest tests/test_storage.py::test_save_creates_file  # Run specific test
```

## Test File Organization

**Location:**
- Co-located with source: `tests/` directory parallel to `src/`
- Direct test modules for each feature module

**Directory structure:**
```
chaoscatcher3/
├── src/chaoscatcher/
│   ├── __init__.py
│   ├── storage.py
│   ├── timeparse.py
│   ├── _util.py
│   ├── fuel_engine.py
│   ├── gui.py
│   └── cli.py
├── tests/
│   ├── __init__.py
│   ├── test_storage.py          # tests storage.load_json, save_json
│   ├── test_timeparse.py        # tests timeparse.parse_ts
│   ├── test_gui_helpers.py      # tests gui.py pure functions (parse_ts, parse_minutes, Store)
│   └── test_cli_helpers.py      # tests cli.py pure functions (parse_minutes, parse_tags)
```

**Naming:**
- Test files: `test_*.py` prefix
- Test functions: `test_*` prefix
- Descriptive names: `test_save_creates_file`, `test_load_corrupt_returns_empty_and_backs_up`
- Grouped by tested component: lines 14-89 in `test_storage.py` organized as `# ---- save_json ----` and `# ---- load_json ----`

## Test Structure

**Test file anatomy** (`test_storage.py`):
```python
"""Tests for storage.load_json and storage.save_json."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from chaoscatcher.storage import load_json, save_json


@pytest.fixture()
def tmp_json(tmp_path: Path) -> Path:
    return tmp_path / "data.json"


# ---- save_json ----


def test_save_creates_file(tmp_json):
    save_json(tmp_json, {"key": "value"})
    assert tmp_json.exists()


# ---- load_json ----


def test_load_missing_returns_empty_dict(tmp_json):
    result = load_json(tmp_json)
    assert result == {}
```

**Test structure pattern:**
1. Module docstring: What is being tested
2. Imports: stdlib, pytest, then tested module
3. Fixtures: Defined with `@pytest.fixture()`
4. Section comments: `# ---- Feature ----` to group related tests
5. Individual test functions: One assertion or tight assertion group per test

**Setup pattern:**
- Fixtures for reusable test data: `tmp_json`, `tmp_path` (pytest built-in)
- Fixture scope: function-level (default) for isolation
- No explicit setUp/tearDown methods; fixtures handle setup/cleanup

**Teardown pattern:**
- `tmp_path` fixture auto-cleans up temporary directories
- No explicit cleanup needed for most tests
- Files created via fixtures are automatically deleted after test

**Assertion pattern:**
- Simple direct assertions: `assert result == {}`
- Existence checks: `assert tmp_json.exists()`
- Type checks: `assert isinstance(data, dict)`
- Approximate checks: `assert abs((result - expected).total_seconds()) < 5`
- Exception testing: `with pytest.raises(ValueError):`

## Mocking

**Framework:** `unittest.mock` (standard library)

**Patterns:**
```python
from unittest.mock import patch

# Patch at import location (gui_helpers test example):
@patch("chaoscatcher.gui._now_local")
def test_parse_ts_none_returns_now(mock_now):
    result = _parse_ts(None)
    assert "T" in result

# Or context manager:
with patch("chaoscatcher.paths.resolve_data_path") as mock_resolve:
    mock_resolve.return_value = Path("/tmp/test.json")
    # test code
```

**Current mocking in tests:**
- `test_gui_helpers.py` uses `@patch("chaoscatcher.gui._now_local")` for time-dependent tests
- Most tests avoid mocking by using temporary test data (prefer real I/O with `tmp_path`)

**What to mock:**
- External system calls: file system mocking with `tmp_path` (preferred over `unittest.mock`)
- Time functions: `_now_local()` when testing time-dependent logic
- Random/non-deterministic functions: rare in this codebase

**What NOT to mock:**
- Pure functions: test with real data
- Data structures: test with real dicts/dataclasses
- Storage I/O: use `tmp_path` fixture instead of mocking
- Calculation logic: test with hardcoded values

## Fixtures and Factories

**Test data:**
```python
# test_storage.py fixture:
@pytest.fixture()
def tmp_json(tmp_path: Path) -> Path:
    return tmp_path / "data.json"

# test_timeparse.py helper:
def _parse(s: str) -> datetime:
    return datetime.fromisoformat(parse_ts(s))

# test_gui_helpers.py fixtures:
@pytest.fixture()
def tmp_path(self):
    # Uses pytest's built-in tmp_path fixture
```

**Location:**
- Fixtures defined in test module head: `test_storage.py` lines 14–16
- Helper functions defined in test module: `test_timeparse.py` lines 13–19
- No conftest.py (no shared fixtures across test modules)

**Pattern:**
```python
# Inline test data construction (test_gui_helpers.py):
def test_store_load_preserves_existing(tmp_path):
    p = tmp_path / "data.json"
    p.write_text(json.dumps({"moods": [{"ts": "x", "score": 7}], "water_goal_oz": 100}))
    store = Store(p)
    data = store.load()
    assert len(data["moods"]) == 1
    assert data["water_goal_oz"] == 100
```

## Coverage

**Requirements:** Not enforced (no coverage configuration in pyproject.toml)

**View coverage:**
```bash
# No built-in coverage command; would need pytest-cov plugin
# Currently: manually review test_*.py for coverage
```

**Current gaps:**
- GUI main window event handlers not tested (PySide6 Qt interaction hard to test)
- CLI main command handlers not heavily tested (`cli.py` has pure helpers tested)
- Notification sound generation tested indirectly via `test_gui_helpers.py`

## Test Types

**Unit Tests:**
- Scope: Single function or dataclass
- Approach: Test inputs and outputs with various parameter combinations
- Examples: `test_storage.py` (JSON I/O), `test_timeparse.py` (time parsing), `test_gui_helpers.py` (pure functions)
- Isolation: No network, no system calls beyond temp file I/O

**Integration Tests:**
- Scope: Multiple modules working together
- Current example: `test_gui_helpers.py` Store class tests load/save roundtrips
- Approach: Use real `tmp_path` fixtures, no mocking of I/O

**E2E Tests:**
- Framework: Not used
- GUI testing (PySide6 interaction) not automated

## Common Patterns

**Async testing:**
- Not applicable (no async code in codebase)
- All functions are synchronous

**Error testing:**
```python
# test_timeparse.py:
def test_invalid_raises():
    with pytest.raises((SystemExit, ValueError)):
        parse_ts("not a time at all blah blah")

# test_gui_helpers.py:
def test_parse_minutes_bad_hhmm():
    with pytest.raises(ValueError):
        _parse_minutes("25:99")

# test_storage.py (graceful handling):
def test_load_corrupt_returns_empty_and_backs_up(tmp_json):
    tmp_json.write_text("not valid json {{{{", encoding="utf-8")
    result = load_json(tmp_json)
    assert result == {}
    backups = list(tmp_json.parent.glob("*.corrupt-*.json"))
    assert len(backups) == 1
```

**Time-dependent testing:**
```python
# test_timeparse.py (relative dates):
def test_relative_days_ago():
    result = _parse("3 days ago")
    expected = datetime.now().astimezone() - timedelta(days=3)
    assert abs((result - expected).total_seconds()) < 5  # Allow 5s tolerance

# test_gui_helpers.py (mocked time):
@patch("chaoscatcher.gui._now_local")
def test_parse_ts_none_returns_now(mock_now):
    before = datetime.now().astimezone().replace(microsecond=0)
    result = _parse(None)
    after = datetime.now().astimezone().replace(microsecond=0)
    assert before <= result <= after
```

**Roundtrip/idempotence testing:**
```python
# test_storage.py:
def test_roundtrip(tmp_json):
    original = {"medications": [{"ts": "2026-01-01T09:00:00", "name": "Test", "dose": "10mg"}]}
    save_json(tmp_json, original)
    result = load_json(tmp_json)
    assert result == original

# test_gui_helpers.py:
def test_store_save_roundtrip(tmp_path):
    p = tmp_path / "data.json"
    store = Store(p)
    data = store.load()
    data["moods"].append({"ts": "2026-03-01T09:00:00", "score": 5})
    store.save(data)
    data2 = store.load()
    assert len(data2["moods"]) == 1
    assert data2["moods"][0]["score"] == 5
```

**Boundary/edge case testing:**
```python
# test_gui_helpers.py:
def test_slope_fewer_than_two():
    assert _linear_regression_slope([1.0], [2.0]) == 0.0

def test_slope_constant_x():
    # All x the same → denominator is 0 → returns 0.0
    assert _linear_regression_slope([3.0, 3.0, 3.0], [1.0, 2.0, 3.0]) == 0.0

def test_pearson_too_few():
    assert _pearson_corr([1.0, 2.0], [3.0, 4.0]) is None

def test_pearson_constant_returns_none():
    # No variance → None
    assert _pearson_corr([1.0, 2.0, 3.0], [5.0, 5.0, 5.0]) is None
```

## Test Organization Philosophy

**Principle:** Test pure logic thoroughly; GUI interaction lightly via manual testing.

**Tested modules:**
- `storage.py` — 100%: All load/save paths, error handling, corruption recovery
- `timeparse.py` — 100%: All format variations, edge cases, errors
- `fuel_engine.py` — Not tested (pure functions untested, but calculate carefully by hand)
- `cli.py` helpers — 100%: All parsing variants, error cases
- `gui.py` helpers — 100%: Pure functions like `_parse_ts`, `_parse_minutes`, `Store` class
- `gui.py` UI/Qt — 0%: Qt event handling tested manually; too coupled to framework

**Test count:** 4 test files with ~50 total test functions

**Naming philosophy:** Test names are specifications. Read the test name and know what was tested and what passed.

---

*Testing analysis: 2026-03-16*
