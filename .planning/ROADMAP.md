# Roadmap: ChaosCatcher 3 (Open Source)

## Overview

ChaosCatcher 3 goes from a rough monolith to a polished, modular, open-source regulation tracker. The journey: apply a cohesive dark theme to the monolith first (easier before splitting), then centralize constants, then break the 3000+ line gui.py into clean modules, then verify everything works, then add the nervous system engine and Regulation tab as the differentiating feature, and finally package it for open source release.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Theme Foundation** - Apply cohesive dark slate theme and centralize all color/style definitions
- [ ] **Phase 2: Models & Constants** - Centralize entry types, colors, and constants into models.py
- [ ] **Phase 3: Modular Extraction** - Split gui.py monolith into views/, dialogs/, widgets/ modules
- [ ] **Phase 4: Visual Consistency** - Enforce consistent spacing, margins, and alignment across all views
- [ ] **Phase 5: Entry Flow Verification** - Verify all entry CRUD operations work correctly across all types
- [ ] **Phase 6: Cross-View Wiring** - Verify and fix all cross-view refresh chains after refactor
- [ ] **Phase 7: Nervous System Engine** - Port and adapt detection engine for load scoring, drift, and dip classification
- [ ] **Phase 8: Regulation Tab** - Build the Regulation tab UI with pre-crash warnings and supportive language
- [ ] **Phase 9: Open Source Release** - README, packaging, contributing guide, and screenshots

## Phase Details

### Phase 1: Theme Foundation
**Goal**: The entire app looks like one cohesive dark-themed application, not a patchwork of inconsistent styles
**Depends on**: Nothing (first phase)
**Requirements**: VIS-01, VIS-02
**Success Criteria** (what must be TRUE):
  1. Every tab in the app renders with the dark slate background (#1E293B) and light text (#F8FAFC)
  2. A single theme.py module defines all colors, and no view/widget code contains hardcoded hex values
  3. Changing a color in theme.py changes it everywhere in the app
**Plans**: TBD

Plans:
- [ ] 01-01: TBD
- [ ] 01-02: TBD

### Phase 2: Models & Constants
**Goal**: All entry types, type-specific colors, and shared constants live in one authoritative module
**Depends on**: Phase 1
**Requirements**: CODE-02
**Success Criteria** (what must be TRUE):
  1. models.py defines all entry type constants (medication, mood, sleep, hydration, fuel, focus)
  2. Entry-type colors are defined in models.py and imported by theme.py and view code (not duplicated)
  3. No other module defines its own entry type strings or color mappings
**Plans**: TBD

Plans:
- [ ] 02-01: TBD

### Phase 3: Modular Extraction
**Goal**: The gui.py monolith is gone, replaced by clean views/, dialogs/, and widgets/ packages
**Depends on**: Phase 2
**Requirements**: CODE-01
**Success Criteria** (what must be TRUE):
  1. gui.py no longer exists (or is reduced to an import shim under 50 lines)
  2. No single Python file exceeds 500 lines
  3. Each tab has its own view module in views/ (meds_view.py, mood_view.py, etc.)
  4. Each entry dialog has its own module in dialogs/
  5. Shared widgets (arc bar, timeline, mood graph, etc.) each have their own module in widgets/
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD
- [ ] 03-03: TBD
- [ ] 03-04: TBD
- [ ] 03-05: TBD

### Phase 4: Visual Consistency
**Goal**: The app has uniform visual rhythm -- spacing, margins, and alignment feel intentional across every view
**Depends on**: Phase 3
**Requirements**: VIS-03
**Success Criteria** (what must be TRUE):
  1. All views use consistent content margins and widget spacing (defined in theme.py or a layout constants module)
  2. Headers, labels, and entry rows are visually aligned across tabs
  3. Scrollable areas behave consistently (same scroll policy, same padding)
**Plans**: TBD

Plans:
- [ ] 04-01: TBD

### Phase 5: Entry Flow Verification
**Goal**: Every entry type can be created, edited, and deleted without errors or data loss
**Depends on**: Phase 3
**Requirements**: CODE-03
**Success Criteria** (what must be TRUE):
  1. User can add a new entry for each type (medication, mood, sleep, hydration, fuel, focus) and see it appear in the correct view
  2. User can edit an existing entry and see the changes persist after restart
  3. User can delete an entry and confirm it is removed from the view and the JSON file
  4. No entry operation corrupts the JSON data file or loses other entries
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD

### Phase 6: Cross-View Wiring
**Goal**: Actions in one view correctly update all dependent views without manual refresh
**Depends on**: Phase 5
**Requirements**: CODE-04
**Success Criteria** (what must be TRUE):
  1. Logging a medication entry updates the Vyvanse arc display in the header
  2. Logging a mood entry updates the mood graph in Stats view
  3. Logging a fuel entry updates the fuel nudge banner
  4. Switching tabs always shows current data (no stale state)
**Plans**: TBD

Plans:
- [ ] 06-01: TBD

### Phase 7: Nervous System Engine
**Goal**: A pure-Python detection engine computes nervous system load, detects drift/spikes, and classifies dips
**Depends on**: Phase 2
**Requirements**: REG-01, REG-02, REG-03
**Success Criteria** (what must be TRUE):
  1. Given mood, sleep, and body signal entries, the engine returns a numeric load score (0-100)
  2. The engine detects slow mood drift (gradual decline over 3+ days) and reactive spikes (sharp single-entry drops)
  3. The engine classifies dips as body-led, emotion-led, or mixed based on contributing signals
  4. The engine works with CC3's plain dict data format (not CCP's Entry dataclass)
**Plans**: TBD

Plans:
- [ ] 07-01: TBD
- [ ] 07-02: TBD
- [ ] 07-03: TBD

### Phase 8: Regulation Tab
**Goal**: Users have a dedicated Regulation tab that shows their nervous system state with early warnings and supportive guidance
**Depends on**: Phase 7
**Requirements**: REG-04, REG-05
**Success Criteria** (what must be TRUE):
  1. The Regulation tab displays current load score with a visual indicator
  2. When multiple vulnerability signals converge, a pre-crash early warning appears with an explanation of what the system sees
  3. All alerts and messages use regulation-centered language (supportive, explainable, never clinical or judgmental)
  4. The tab explains its reasoning -- users can see what data contributed to any assessment
**Plans**: TBD

Plans:
- [ ] 08-01: TBD
- [ ] 08-02: TBD

### Phase 9: Open Source Release
**Goal**: A stranger can discover, understand, install, and run ChaosCatcher 3 from the GitHub repo
**Depends on**: Phase 8
**Requirements**: OSS-01, OSS-02, OSS-03
**Success Criteria** (what must be TRUE):
  1. README includes clear description, screenshots of the app, and step-by-step install instructions
  2. Running `pip install .` from the repo root installs the app and its dependencies via pyproject.toml
  3. CONTRIBUTING.md explains how to set up a dev environment, run tests, and follow code conventions
  4. A new user with Python 3.10+ can go from git clone to running app in under 5 minutes
**Plans**: TBD

Plans:
- [ ] 09-01: TBD
- [ ] 09-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9
Note: Phases 4, 5, and 6 all depend on Phase 3. Phases 5 and 6 are sequential (wiring depends on flows working). Phase 7 depends only on Phase 2 (pure domain logic), but practically runs after Phase 6 so the app is stable.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Theme Foundation | 0/2 | Not started | - |
| 2. Models & Constants | 0/1 | Not started | - |
| 3. Modular Extraction | 0/5 | Not started | - |
| 4. Visual Consistency | 0/1 | Not started | - |
| 5. Entry Flow Verification | 0/2 | Not started | - |
| 6. Cross-View Wiring | 0/1 | Not started | - |
| 7. Nervous System Engine | 0/3 | Not started | - |
| 8. Regulation Tab | 0/2 | Not started | - |
| 9. Open Source Release | 0/2 | Not started | - |
