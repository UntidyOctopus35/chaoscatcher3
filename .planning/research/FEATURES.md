# Feature Research

**Domain:** Personal health/regulation tracking (open source desktop app)
**Researched:** 2026-03-16
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Consistent dark theme | Every modern health app has cohesive styling | MEDIUM | Currently rough/inconsistent — #1 visual issue |
| Mood logging with scale + notes | Core function of any mood tracker | LOW | Already exists, needs polish |
| Medication tracking with timing | Basic health app functionality | LOW | Already exists with Vyvanse arc |
| Sleep logging | Sleep is foundational to regulation | LOW | Already exists with stages |
| Data visualization (mood graphs) | Users need to see patterns, not just log | MEDIUM | Exists but could be more readable |
| Data export (CSV/JSON) | Users expect data portability | LOW | Already exists |
| No data lock-in / local-only | Open source users care deeply about this | LOW | Already a core principle |
| Keyboard shortcuts / low-friction entry | Health app that's annoying to use won't get used | MEDIUM | Partially exists — needs audit |
| Undo / edit / delete entries | Mistakes happen, especially with brain fog | LOW | Needs verification across all types |

### Differentiators (Competitive Advantage)

Features that set the product apart from generic mood trackers.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Nervous system load scoring | No other OSS tool does this — translates signals into actionable awareness | HIGH | Port from CCP's nervous_system.py |
| Regulation-centered language | Supportive tone instead of clinical/judgmental — designed for neurodivergent users | LOW | Tone rules already defined in CCP |
| Drift / spike detection | Catches slow slides and reactive spikes that users miss in the moment | MEDIUM | Pure detection logic from CCP |
| Pre-crash early warning | Converging vulnerability signals flagged before crash hits | MEDIUM | Multi-channel detection from CCP |
| Dip classification (body vs emotion) | Helps user respond appropriately — rest vs grounding vs both | MEDIUM | Already implemented in CCP |
| Fuel nudge engine | Smart food/hydration reminders based on actual patterns | LOW | Already exists in CC3 |
| Vyvanse arc visualization | Phase-based medication tracking with color-coded timeline | LOW | Already exists in CC3 |
| Focus timer integration | Not just mood — complete regulation toolkit | LOW | Already exists |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Gamification / streaks | "Motivates consistent logging" | Creates shame when streaks break — especially harmful for mood disorders | Gentle "it's been a while" nudge, never punishment |
| Social / sharing | "Accountability partners" | Health data is deeply personal, social pressure harms regulation | Keep local-only, export if user chooses to share |
| AI analysis / chatbot | "Interpret my patterns" | Risk of pseudo-diagnosis, privacy concerns, adds cloud dependency | Rule-based detection with explainable reasoning |
| Detailed analytics dashboards | "I want to see everything" | Information overload increases cognitive load — opposite of regulation-centered | Curated, relevant alerts with "why this fired" |
| Notifications for every entry | "Remind me to log everything" | Notification fatigue, feels like a demanding app | Only nudge for fuel/hydration, never for mood/sleep |

## Feature Dependencies

```
[Consistent Theme]
    └──enables──> [All Views Look Professional]

[Refactored Codebase]
    └──enables──> [Regulation Tab Addition]
    └──enables──> [Bug Fixes Across Views]
    └──enables──> [Future Contributors Can Navigate Code]

[Nervous System Engine]
    └──requires──> [Mood Data] (already exists)
    └──requires──> [Sleep Data] (already exists)
    └──enhances──> [Regulation View]

[Regulation View]
    └──requires──> [Nervous System Engine]
    └──requires──> [Interpretation Layer]
    └──requires──> [Refactored Codebase] (to add cleanly as new view)
```

### Dependency Notes

- **Regulation View requires Refactored Codebase:** Adding a new tab to the 3000-line monolith is messy; adding it to a clean views/ structure is trivial
- **Theme should come before refactor:** Easier to apply theme once to monolith, then split — avoids duplicating theme work across new files
- **Nervous System Engine is independent:** Pure Python, no Qt dependency — can be developed/tested in isolation

## MVP Definition

### Launch With (v1 — this milestone)

- [x] Medication, mood, sleep, hydration, fuel, focus tracking — already exists
- [ ] Consistent dark theme across all views — visual polish
- [ ] Clean modular codebase — refactor gui.py monolith
- [ ] Bug-free core functionality — systematic jank removal
- [ ] Regulation tab with load scoring and alerts — key differentiator
- [ ] Professional README with screenshots — OSS first impression

### Add After Validation (v1.x)

- [ ] Pattern visualization improvements — richer mood/sleep graphs
- [ ] Configurable theme colors — let users customize accent palette
- [ ] Task management integration — daily task tracking
- [ ] Improved notification system — smarter timing

### Future Consideration (v2+)

- [ ] Mobile companion (read-only) — view patterns on phone
- [ ] Plugin system — let contributors add tracking types
- [ ] Import from other health apps — data migration tools

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Consistent dark theme | HIGH | MEDIUM | P1 |
| Code refactor (modular) | HIGH (for maintainability) | HIGH | P1 |
| Bug fixes | HIGH | MEDIUM | P1 |
| Regulation tab | HIGH | MEDIUM | P1 |
| README + screenshots | HIGH (for OSS adoption) | LOW | P1 |
| Pattern viz improvements | MEDIUM | MEDIUM | P2 |
| Configurable themes | LOW | LOW | P3 |

## Competitor Feature Analysis

| Feature | Daylio | Bearable | Moodflow | ChaosCatcher |
|---------|--------|----------|----------|--------------|
| Mood tracking | Yes (emoji-based) | Yes (detailed) | Yes (simple) | Yes (1-10 + notes) |
| Medication timing | No | Yes (basic) | No | Yes (Vyvanse arc) |
| Sleep tracking | No | Yes | No | Yes (stages + quality) |
| Nervous system alerts | No | No | No | Yes (differentiator) |
| Regulation language | No (clinical) | No (clinical) | No (neutral) | Yes (supportive) |
| Open source | No | No | No | Yes |
| Offline / local-only | No (cloud) | No (cloud) | No (cloud) | Yes |
| Free | Freemium | Freemium | Freemium | Fully free |

## Sources

- CCPrivate codebase — proven regulation features and design philosophy
- Daylio, Bearable, Moodflow — competitor feature analysis
- Neurodivergent UX research — regulation-centered design principles

---
*Feature research for: Personal health/regulation tracking (open source)*
*Researched: 2026-03-16*
