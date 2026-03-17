# Pitfalls Research

**Domain:** PySide6 health-tracking app refactor + regulation feature addition
**Researched:** 2026-03-16
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Breaking Working Features During Refactor

**What goes wrong:**
Extracting code from gui.py into separate modules introduces subtle bugs — signals disconnected, refresh cycles broken, state not properly shared between views.

**Why it happens:**
The monolith has implicit dependencies: a method in the mood section reads a variable set in the medication section. When split into separate files, these hidden couplings break silently.

**How to avoid:**
- Extract one view at a time, not all at once
- Run the full app after each extraction and manually verify the tab still works
- Write a smoke test for each view before extracting it
- Keep `git diff` small — if an extraction touches > 500 lines, it's too big

**Warning signs:**
- "This variable isn't defined" errors after extraction
- Refresh loops that worked before now show stale data
- Timers or signals that fire but nothing updates

**Phase to address:** Refactor phase — must be incremental, not big-bang

---

### Pitfall 2: Data Format Mismatch Between CCP and CC3

**What goes wrong:**
CCP's nervous_system.py expects `Entry` dataclass objects with `.type`, `.data`, `.dt` attributes. CC3 stores plain dicts in separate lists (`moods`, `medications`, `fuel`, etc.). Porting the detection engine without adapting the data layer produces incorrect results or crashes.

**Why it happens:**
Copy-pasting from CCP without understanding the data model differences. The functions look the same but operate on different shapes.

**How to avoid:**
- Write an explicit adapter function: `cc3_entries_to_detection_format(store_data) -> list[dict]`
- Unit test the adapter with real CC3 data samples
- Verify detection results match expected output before wiring to UI

**Warning signs:**
- KeyError exceptions when detection functions run
- Load score always returns 0 (no entries matched the expected format)
- Mood baseline returns None even with plenty of mood data

**Phase to address:** Nervous system engine phase — adapter must be tested before UI work

---

### Pitfall 3: Theme Inconsistency Across Tabs

**What goes wrong:**
Applying a theme to some tabs but not others. Or applying a base theme that conflicts with inline `setStyleSheet()` calls scattered throughout gui.py.

**Why it happens:**
gui.py has ~50+ inline `setStyleSheet()` calls with hardcoded colors. A global QSS theme gets overridden by these inline styles, creating visual chaos.

**How to avoid:**
- Audit ALL inline setStyleSheet calls before applying a global theme
- Replace inline styles with class-based selectors or remove them in favor of global QSS
- Apply theme BEFORE refactoring views — easier to fix in one file than across 10

**Warning signs:**
- Some widgets use old colors while others use new theme
- Buttons or labels appear with wrong background after theme change
- Hover states inconsistent between different parts of the app

**Phase to address:** Theme phase — must be first, before refactor splits the file

---

### Pitfall 4: Losing the Regulation-Centered Tone

**What goes wrong:**
Alert messages in the Regulation tab use clinical or judgmental language — "Your mood has declined significantly" instead of "Mood is running below your baseline — treat today as a lower-capacity day."

**Why it happens:**
Generic health app patterns creep in. The developer forgets the tone rules and writes alerts that sound like a doctor's report instead of a supportive companion.

**How to avoid:**
- CCP's interpretation.py already has the right tone — port it carefully
- Tone rules: use "may", "appears", "suggests" — never diagnose
- Every alert MUST include "why this fired" (explainability)
- Review all user-facing strings against the tone checklist before shipping

**Warning signs:**
- Words like "failed", "should", "you need to", "warning", "danger"
- Alerts without explanation of why they fired
- Clinical terminology: "significant decline", "abnormal pattern"

**Phase to address:** Regulation tab phase — tone review as acceptance criterion

---

### Pitfall 5: Regression in Entry Logging Flows

**What goes wrong:**
After refactoring, adding a mood entry works but the mood graph doesn't update. Or adding a medication works but the Vyvanse arc chip in the header doesn't refresh.

**Why it happens:**
In the monolith, `_refresh_all_lists()` calls every refresh method in sequence. When views are split, the main window needs to re-wire these refresh chains, and it's easy to miss one.

**How to avoid:**
- Document every refresh dependency before splitting: "logging a med must refresh: med list, vyvanse chip, fuel banner"
- Use Qt signals: each view emits `entry_added` signal, MainWindow connects to refresh dependent views
- Integration test: add entry via each dialog, verify all dependent UI updates

**Warning signs:**
- Data saves correctly (check JSON file) but UI doesn't update
- Need to switch tabs and come back to see new entry
- Some cross-view updates work but others don't

**Phase to address:** Refactor phase — refresh chain mapping is prerequisite to extraction

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep some logic in views during refactor | Faster extraction | Harder to test, duplicated logic | During initial extraction — clean up in dedicated pass |
| Inline styles on new widgets | Quick visual fix | Fights with global theme | Never — always use theme constants |
| Skip adapter tests for nervous system | Ship regulation tab faster | Silent data mismatches, wrong alerts | Never — wrong health alerts are worse than no alerts |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Re-reading entire JSON file on every refresh | Sluggish tab switching | Cache store data, reload on save only | >500 entries (a few months of daily use) |
| Running all detection functions on tab switch | Regulation tab takes seconds to render | Compute on timer (every 5 min) not on every refresh | >200 mood entries |
| Matplotlib redraw on every mood graph update | Graph flickers, CPU spike | Only redraw when data actually changed | Always — matplotlib redraws are expensive |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging file paths in error messages | Reveals user's home directory structure in screenshots/reports | Use relative paths or sanitized messages |
| Not chmod 0600 on data files | Other users on shared system can read health data | storage.py already does this — verify it survives refactor |
| Including real data in screenshots for README | Leaks personal health information | Use synthetic/demo data for all screenshots |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Too many alerts in Regulation tab | Overwhelms user, defeats regulation purpose | Show top 1-2 alerts, collapse rest behind "see more" |
| Alert text too long | Brain fog users can't parse paragraphs | Lead with one-line title, expandable details |
| No explanation of load score | Number without context is meaningless | Always show what contributed: "sleep quality 3/10, fatigue noted" |
| Nudge notifications during high-load state | App adds to cognitive burden during worst moments | Consider muting non-essential nudges when load is high |

## "Looks Done But Isn't" Checklist

- [ ] **Theme:** All tabs use theme colors — check inline styles aren't overriding
- [ ] **Refactor:** All refresh chains work — adding entry in one view updates dependent views
- [ ] **Regulation tab:** Load score returns meaningful results with real data — not just zeroes
- [ ] **Regulation tab:** Alerts use regulation-centered tone — no clinical/judgmental language
- [ ] **Export:** CSV export still works after data model changes — verify column headers
- [ ] **CLI:** CLI commands still work after refactor — they share storage.py
- [ ] **Sleep logging:** Stage minutes don't exceed total sleep — anomaly detection catches this
- [ ] **README:** Screenshots show current UI — not pre-polish version

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Broken refresh chains | LOW | Add missing signal connections in MainWindow |
| Data format mismatch | MEDIUM | Write adapter, add tests, re-run detection suite |
| Theme inconsistency | LOW | Audit all setStyleSheet calls, replace with theme refs |
| Tone violations | LOW | String review pass, update alert text |
| Regression in entry flows | MEDIUM | Bisect git history, restore broken extraction, redo carefully |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Breaking features during refactor | Refactor phase | Manual smoke test after each view extraction |
| Data format mismatch | Nervous system engine phase | Unit tests with real CC3 data samples |
| Theme inconsistency | Theme phase | Visual audit of every tab with new theme |
| Tone violations | Regulation tab phase | String review against tone checklist |
| Regression in entry flows | Refactor phase | Integration test: add entry, verify all updates |

## Sources

- CCPrivate refactoring experience — same monolith-to-modular journey, same pitfalls encountered
- CC3 codebase concerns analysis — identified existing tech debt
- Regulation-centered design philosophy — tone and UX guidelines

---
*Pitfalls research for: PySide6 health-tracking app refactor + regulation features*
*Researched: 2026-03-16*
