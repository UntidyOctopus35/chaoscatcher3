# Codebase Concerns

**Analysis Date:** 2026-03-16

## Tech Debt

**Broad Exception Handling:**
- Issue: 23 instances of bare `except Exception` and one `except BaseException` used for swallowing errors silently, making debugging difficult
- Files: `src/chaoscatcher/gui.py` (lines 100, 205, 740, 769, 856, 1021, 1069, 1147, 1373, 1696, 1704, 1922, 2298, 2333, 2536, 2752, 2782, 3021, 3149, 3167)
- Impact: Silent failures hide bugs and prevent proper error diagnosis. Users won't know when something breaks.
- Fix approach: Replace bare `except Exception` with specific exception types. For UI operations, catch specific errors and provide user feedback via QMessageBox. For data operations, allow exceptions to propagate for logging.

**Monolithic GUI File:**
- Issue: `src/chaoscatcher/gui.py` is 3184 lines, containing MainWindow class with 50+ methods spanning data loading, chart generation, tab building, and event handling
- Files: `src/chaoscatcher/gui.py`
- Impact: Hard to navigate, test, or modify. Single responsibility principle violated. Changes to unrelated features affect entire file.
- Fix approach: Extract logical components into separate classes: TabBuilder, ChartGenerator, StateManager, NotificationHandler. Keep gui.py as light orchestration layer.

**Late Import Within Method:**
- Issue: `import numpy as np` happens inside `_chart_sleep_stages_nightly()` at line 2601, only when that specific chart is rendered
- Files: `src/chaoscatcher/gui.py` (line 2601)
- Impact: Numpy is a heavy dependency; lazy-loading hides dependency from upfront analysis. If numpy is not installed, user only discovers this at chart generation time.
- Fix approach: Move `import numpy` to top of file or make it an explicit optional dependency with fallback. Consider if numpy is necessary for simple bar chart (could use matplotlib only).

**Undocumented State Management:**
- Issue: Focus timer state (_focus_running, _focus_phase, _focus_seconds_left) scattered across MainWindow instance variables with no clear initialization or lifecycle documentation
- Files: `src/chaoscatcher/gui.py` (scattered throughout ~3000 lines)
- Impact: Modifying timer logic requires understanding state across entire class. No single source of truth for what constitutes "valid" timer state.
- Fix approach: Extract FocusSessionState dataclass or FocusSessionManager class to encapsulate all timer state and operations.

## Performance Bottlenecks

**Full Data Reload on Every Modification:**
- Issue: Every entry creation (mood, med, fuel) calls `self.store.load()` then `self.store.save()` and then `self._refresh_all_lists()`, which reloads and re-renders all 7 tabs
- Files: `src/chaoscatcher/gui.py` (throughout, e.g., _med_add, _mood_add, _fuel_add methods)
- Impact: As data grows (months of entries), every single entry creation triggers full JSON reload and UI refresh. With 1000+ entries, this is measurable lag.
- Improvement path: Implement local state sync. Append entry to in-memory list, update JSON, then refresh only affected lists (not all 7 tabs). Cache mood daily averages.

**Naive Correlation Calculations:**
- Issue: Pearson correlation, linear regression, and trend analysis recalculated fresh every time stats tab renders without caching
- Files: `src/chaoscatcher/gui.py` (_pearson_corr, _linear_regression_slope, _chart_* methods)
- Impact: Opening stats tab with months of data does O(n) calculations every time. No memoization or caching.
- Improvement path: Cache computed correlations keyed by (data_window, entry_type) with invalidation on new entries.

**Datetime Parsing on Every Entry Display:**
- Issue: `_dt_from_entry_ts()` called per entry in lists, parsing ISO string to datetime for every row
- Files: `src/chaoscatcher/gui.py`, `src/chaoscatcher/cli.py`
- Impact: Displaying 100+ entries means 100+ datetime.fromisoformat() calls.
- Improvement path: Parse once when loading data, store as datetime, convert back to ISO only for storage.

## Fragile Areas

**TimeZone Awareness Inconsistency:**
- Issue: Multiple functions handle timezone conversion (_with_local_tz, _dt_from_entry_ts, astimezone() calls) with slightly different approaches
- Files: `src/chaoscatcher/_util.py` (lines 20-27), `src/chaoscatcher/timeparse.py` (lines 11-14, 104-126)
- Why fragile: Different code paths may treat naive timestamps differently. Edge cases around daylight saving time transitions could cause entries to appear on wrong dates.
- Safe modification: Centralize timezone handling. Define one canonical function that all code uses. Add tests for DST transitions.
- Test coverage: No tests for timezone/DST behavior

**Time Parsing Multiple Formats Without Validation:**
- Issue: `parse_ts()` tries 10+ datetime format strings sequentially with try/except. Order matters; early matches may consume input incorrectly
- Files: `src/chaoscatcher/timeparse.py` (lines 74-95)
- Why fragile: Ambiguous input like "02/03/04" could parse differently depending on locale/format order. No validation that parsed result makes sense.
- Safe modification: Be explicit about format expectations. Consider requiring ISO format for programmatic use. Document expected formats.
- Test coverage: Test file exists but edge cases around format ambiguity not covered

**Exception Handling Doesn't Distinguish Errors:**
- Issue: Most `except Exception` blocks have identical responses regardless of actual error. File I/O errors treated same as parsing errors.
- Files: `src/chaoscatcher/gui.py` (throughout)
- Why fragile: Cannot distinguish recoverable errors from data corruption. User sees generic "Error" message for all failures.
- Safe modification: Create exception hierarchy (ParseError, StorageError, ValidationError) and handle each appropriately.
- Test coverage: Error paths not tested

## Scaling Limits

**JSON File as Single Source of Truth:**
- Current capacity: Works up to ~10,000 entries (hundreds of KB JSON file)
- Limit: Beyond 10K entries, JSON parsing + full reload on each modification becomes noticeable lag. No transaction support.
- Scaling path: Consider migration path to SQLite for entries while keeping JSON config. Implement incremental sync instead of full reload.

**Chart Generation Rendering Entire History:**
- Current capacity: Stats tab can display 30 days of charts smoothly
- Limit: 1+ years of daily charts causes matplotlib to struggle with rendering performance
- Scaling path: Implement windowed chart queries. For "all time" views, aggregate data (week/month buckets).

## Missing Critical Features

**No Data Validation on Load:**
- Problem: Missing required fields (ts, type) silently ignored. Entries with invalid data (score > 10, negative water oz) accepted without warning.
- Files: `src/chaoscatcher/gui.py` (Store.load(), throughout list builders)
- Blocks: Cannot detect data corruption early. Users may not notice bad data until analysis stage.
- Recommendation: Implement Entry/MoodEntry/FuelEntry validator. Reject or coerce invalid data during load. Log warnings for skipped entries.

**No Offline Conflict Resolution:**
- Problem: If data.json is modified externally (user opens backup in another instance), last write wins, data is lost
- Files: `src/chaoscatcher/storage.py` (load_json/save_json)
- Blocks: Prevents safe multi-device use or manual backups
- Recommendation: Implement simple conflict detection (check file mtime before save, warn if changed). Consider JSON Patch format for incremental syncing.

**No Entry Edit History:**
- Problem: Once an entry is logged, there's no way to see what the original value was if user modifies it later
- Impact: For health tracking (mood, sleep), audit trail important for analyzing trends
- Fix approach: When modifying entry, keep previous version in "history" array within entry, or log deletion + re-add with original timestamps

## Security Considerations

**File Permissions but No Content Encryption:**
- Risk: `data.json` contains complete medication, mood, and health history. Stored with 0o600 permissions but unencrypted on disk.
- Files: `src/chaoscatcher/storage.py` (line 77)
- Current mitigation: File permissions prevent other local users from reading. No network transmission.
- Recommendations: Add optional encryption at rest. Document that no encryption currently in place. For WSL2 users, warn that Windows can access WSL filesystem.

**Git Repo Detection but No .gitignore Enforcement:**
- Risk: User might commit data.json to git if using --allow-repo-data-path
- Files: `src/chaoscatcher/safety.py` (lines 18-29)
- Current mitigation: Warnings printed, but user can override. No automatic .gitignore update.
- Recommendations: If user stores data in repo, automatically add entry to .gitignore. Require explicit confirmation for repo data paths.

**No Input Sanitization on Notes Fields:**
- Risk: Arbitrary text in medication/mood notes could contain sensitive information that leaks in exports or backups
- Files: `src/chaoscatcher/gui.py` (export functions), throughout entry creation
- Impact: Low risk (local-first, user controls their data) but good practice
- Recommendation: Clarify in UI that notes are stored plaintext. Consider warning before exporting.

## Test Coverage Gaps

**Core Entry Logic Untested:**
- What's not tested: Creating entries, loading from JSON, formatting for display, all entry operations
- Files: `src/chaoscatcher/gui.py` (entire _med_add, _mood_add, _fuel_add, etc.)
- Risk: Breaking changes to entry structure not caught until user notices
- Priority: High - these are critical paths

**Chart Generation Untested:**
- What's not tested: Mood correlation calculations, sleep stage percentages, any chart rendering
- Files: `src/chaoscatcher/gui.py` (_chart_* methods)
- Risk: Bad data or edge cases (no entries, negative values, division by zero) could crash stats tab
- Priority: Medium - users will notice when stats tab breaks

**Time Parsing Edge Cases Untested:**
- What's not tested: DST transitions, midnight edge cases, year boundaries, ambiguous formats
- Files: `src/chaoscatcher/timeparse.py` (test_timeparse.py exists but incomplete)
- Risk: Entries could appear on wrong date during certain time window changes
- Priority: Medium-High - affects data integrity

**Focus Timer State Not Tested:**
- What's not tested: Timer tick accuracy, session rollover, pause/resume, sound generation
- Files: `src/chaoscatcher/gui.py` (_focus_tick, _focus_start_pause, _focus_play_sound)
- Risk: Timer bugs silently affect user's productivity tracking
- Priority: Low-Medium - primarily UX impact

**Export Format Stability Not Tested:**
- What's not tested: CSV export with special characters, JSON roundtrip with unicode, export of empty/malformed entries
- Files: `src/chaoscatcher/gui.py` (_export_json_as, _export_fuel_csv)
- Risk: Exports may be corrupted, preventing data recovery
- Priority: High - affects data portability

## Known Limitations

**Windows Path Handling in Audio:**
- Issue: `_focus_play_sound()` uses Linux `paplay` command, only works on Linux/WSL2
- Files: `src/chaoscatcher/gui.py` (line 3019)
- Workaround: On Windows native, audio fails silently (caught by bare except)
- Status: By design (WSL2-first development), but limits cross-platform use

**Numpy Dependency Hidden:**
- Issue: Charts use numpy but it's not in `dependencies` in pyproject.toml, only discovered at runtime if user wants stacked bar charts
- Files: `pyproject.toml`, `src/chaoscatcher/gui.py` (line 2601)
- Workaround: None currently; if numpy missing, stats tab charts fail
- Status: Should add numpy to dependencies or remove chart type that requires it

---

*Concerns audit: 2026-03-16*
