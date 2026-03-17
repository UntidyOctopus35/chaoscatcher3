# Research Summary

**Project:** ChaosCatcher 3 (Open Source)
**Researched:** 2026-03-16

## Key Findings

### Stack
- **Keep everything currently in use** — PySide6, matplotlib, JSON storage, pytest, ruff
- **One optional addition:** qt-material for base dark theme (or pure QSS for full control)
- **No new heavy dependencies** — the nervous system engine is pure Python ported from CCP
- **Avoid:** PyQt6 (GPL), QML (overkill), SQLAlchemy (overkill), Electron (defeats purpose)

### Table Stakes (Must Fix)
- Consistent dark theme across all tabs (currently rough/inconsistent)
- Clean modular code (3000+ line gui.py is unmaintainable for OSS)
- Bug-free core flows (jank across entry logging, refresh chains)
- Professional README with screenshots (first impression for OSS users)

### Differentiators (What Makes CC3 Special)
- **Nervous system load scoring** — no other OSS tool does this
- **Regulation-centered language** — supportive, never clinical or judgmental
- **Drift/spike detection** — catches patterns users miss in the moment
- **Pre-crash early warnings** — converging vulnerability signals flagged before crash hits
- **Dip classification** — body-led vs emotion-led, guides appropriate response

### Architecture Direction
- Split gui.py into `views/`, `dialogs/`, `widgets/` (proven pattern from CCP)
- Add `models.py` for centralized types, `theme.py` for centralized styling
- Pure domain modules for detection engine (no Qt dependency)
- Incremental extraction: one view at a time, working commit after each

### Watch Out For
1. **Big-bang refactor** — extract one view at a time, not all at once
2. **Data format mismatch** — CC3 uses plain dicts, CCP uses Entry dataclass; need adapter
3. **Theme conflicts** — ~50+ inline setStyleSheet calls will fight a global theme
4. **Broken refresh chains** — cross-view updates (log med → update arc chip) must be re-wired
5. **Tone violations** — regulation alerts must use supportive language, never clinical

### Build Order Recommendation
1. Theme (apply to monolith — easier before split)
2. Extract models/constants
3. Extract widgets
4. Extract views (one at a time, simplest first)
5. Slim main_window.py
6. Add nervous system engine + adapter
7. Add Regulation tab
8. Bug fixes + polish
9. README + screenshots

## Research Files

| File | Lines | What It Covers |
|------|-------|----------------|
| STACK.md | ~100 | Technologies, what to keep/add/avoid |
| FEATURES.md | ~150 | Table stakes, differentiators, anti-features, competitor analysis |
| ARCHITECTURE.md | ~200 | Target structure, patterns, data flow, build order |
| PITFALLS.md | ~200 | Refactoring risks, data pitfalls, UX traps, recovery strategies |

---
*Research summary for: ChaosCatcher 3 (Open Source)*
*Synthesized: 2026-03-16*
