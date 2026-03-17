# ChaosCatcher 3 (Open Source)

## What This Is

ChaosCatcher is an open-source personal regulation-tracking desktop app that helps people translate internal brain and body signals into visible patterns. It tracks medication timing, mood, sleep, hydration, fuel (food), and focus sessions. Built with Python and PySide6, it runs fully offline with local-only JSON storage.

## Core Value

Help users stay stable, aware, and regulated by making invisible nervous-system patterns visible — with zero friction and zero judgment.

## Requirements

### Validated

- ✓ Medication logging with Vyvanse arc tracking — existing
- ✓ Mood logging with 1-10 scale and notes — existing
- ✓ Sleep logging with stages and quality — existing
- ✓ Hydration tracking with daily goals — existing
- ✓ Fuel (food) logging with nudge engine — existing
- ✓ Focus timer with Pomodoro-style sessions — existing
- ✓ Stats view with mood graphs and summaries — existing
- ✓ CSV/JSON export — existing
- ✓ CLI interface for all tracking types — existing
- ✓ Desktop notifications via PowerShell on WSL2 — existing

### Active

- [ ] Visual polish — cohesive dark theme, consistent spacing, professional feel
- [ ] Code refactor — break 3000+ line gui.py monolith into modular views/dialogs/widgets
- [ ] Bug hunt and fix — systematic pass through all features for jank and breakage
- [ ] Regulation tab — nervous system load scoring, drift detection, dip classification, pre-crash warnings
- [ ] Open source polish — README, screenshots, easy install experience

### Out of Scope

- Substance/hemp tracking — private version only, not appropriate for public release
- Cloud sync — local-first philosophy, no external services
- Mobile app — desktop-first, PySide6 only for now
- User accounts / auth — single-user local app

## Context

ChaosCatcher 3 is the open-source sibling of a private version (CCPrivate/CCP) that has more advanced features including substance tracking and a nervous system interpretation layer. The goal for this milestone is to bring CC3 up to a quality level where it's something to be proud of publicly — polished visuals, clean modular code, no embarrassing bugs — and then add the Regulation tab as the differentiating feature that makes CC3 genuinely useful for anyone managing their nervous system.

The private version already has a working nervous system detection engine (`nervous_system.py`) and interpretation layer (`interpretation.py`) that are substance-free and can be adapted for CC3's data model (plain dicts vs CCP's Entry dataclass).

The current codebase has a 3000+ line `gui.py` monolith that contains all tabs, dialogs, widgets, and business logic in a single file. CCP has already been refactored into a clean `views/`, `dialogs/`, `widgets/` structure that works well and should serve as the target architecture.

**Target audience:** People with ADHD, mood disorders, or anyone who wants to understand their body/brain patterns better. The app should feel calm, supportive, and never judgmental.

## Constraints

- **Stack**: Python 3.10+, PySide6, matplotlib — no new heavy dependencies
- **Compatibility**: Must preserve existing JSON data files — no breaking changes to storage format
- **Platform**: Must work on Linux (primary), WSL2, and ideally native Windows/macOS
- **Design**: Dark theme, regulation-centered — interfaces should reduce cognitive load
- **Tone**: Nudges and alerts use supportive language — never "failed", "should", "overdue"

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Break gui.py into views/dialogs/widgets | 3000+ line monolith is unmaintainable for OSS contributors | — Pending |
| Adapt CCP's nervous_system.py for CC3 | Already proven logic, substance-free, just needs data model adapter | — Pending |
| Visual + refactor before new features | Solid foundation makes Regulation tab addition cleaner | — Pending |
| Keep JSON flat-file storage | Simple, no dependencies, backwards compatible | ✓ Good |

---
*Last updated: 2026-03-16 after initialization*
