# Requirements: ChaosCatcher 3

**Defined:** 2026-03-16
**Core Value:** Help users stay stable, aware, and regulated by making invisible nervous-system patterns visible -- with zero friction and zero judgment.

## v1 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Visual Polish

- [ ] **VIS-01**: App uses consistent dark slate theme (#1E293B backgrounds, #F8FAFC text) across all tabs
- [ ] **VIS-02**: All colors defined in centralized theme module -- no hardcoded hex in view/widget code
- [ ] **VIS-03**: Consistent spacing, margins, and alignment across all views

### Code Quality

- [ ] **CODE-01**: gui.py monolith split into views/, dialogs/, widgets/ modules -- no single file > 500 lines
- [ ] **CODE-02**: Entry types, colors, and constants centralized in models.py
- [ ] **CODE-03**: All entry logging flows verified working (add, edit, delete for each type)
- [ ] **CODE-04**: All cross-view refresh chains verified (logging entry updates dependent views)

### Regulation

- [ ] **REG-01**: Nervous system load score computed from mood, sleep, body signals, and triggers
- [ ] **REG-02**: Drift and spike detection identifies slow mood slides and reactive emotional spikes
- [ ] **REG-03**: Dip classification determines body-led vs emotion-led vs mixed
- [ ] **REG-04**: Pre-crash early warning when multiple vulnerability signals converge
- [ ] **REG-05**: All alerts use regulation-centered language (supportive, explainable, never clinical)

### Open Source

- [ ] **OSS-01**: README with screenshots, clear description, and install instructions
- [ ] **OSS-02**: pip install chaoscatcher works from pyproject.toml
- [ ] **OSS-03**: CONTRIBUTING.md with setup instructions and code conventions

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Visualization

- **VIZ-01**: Richer mood/sleep pattern graphs with trend lines
- **VIZ-02**: Configurable theme colors (user-selectable accent palette)

### Integration

- **INT-01**: Task management integration (daily task tracking)
- **INT-02**: Improved notification timing (context-aware)

### Platform

- **PLAT-01**: Mobile companion app (read-only pattern viewer)
- **PLAT-02**: Data import from other health apps

## Out of Scope

| Feature | Reason |
|---------|--------|
| Substance/hemp tracking | Private version only -- not appropriate for public release |
| Cloud sync | Local-first philosophy, no external service dependencies |
| AI/LLM analysis | Risk of pseudo-diagnosis, privacy concerns, adds cloud dependency |
| Social/sharing features | Health data is deeply personal, social pressure harms regulation |
| Gamification/streaks | Creates shame when broken -- harmful for mood disorders |
| Real-time notifications for all entry types | Notification fatigue, only nudge for fuel/hydration |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| VIS-01 | Phase 1 | Pending |
| VIS-02 | Phase 1 | Pending |
| VIS-03 | Phase 4 | Pending |
| CODE-01 | Phase 3 | Pending |
| CODE-02 | Phase 2 | Pending |
| CODE-03 | Phase 5 | Pending |
| CODE-04 | Phase 6 | Pending |
| REG-01 | Phase 7 | Pending |
| REG-02 | Phase 7 | Pending |
| REG-03 | Phase 7 | Pending |
| REG-04 | Phase 8 | Pending |
| REG-05 | Phase 8 | Pending |
| OSS-01 | Phase 9 | Pending |
| OSS-02 | Phase 9 | Pending |
| OSS-03 | Phase 9 | Pending |

**Coverage:**
- v1 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0

---
*Requirements defined: 2026-03-16*
*Last updated: 2026-03-16 after roadmap creation*
