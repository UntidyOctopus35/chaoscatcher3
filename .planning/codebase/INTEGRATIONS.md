# External Integrations

**Analysis Date:** 2026-03-16

## APIs & External Services

**None.**

ChaosCatcher is a local-first application with zero external API dependencies. No cloud services, SaaS integrations, or remote APIs are used.

## Data Storage

**Databases:**
- Not applicable — no SQL or database server

**File Storage:**
- Local filesystem only
- Default location: `~/.config/chaoscatcher/data.json`
- Format: JSON (flat-file, line-delimited entries)
- Access: Direct file read/write via `src/chaoscatcher/storage.py`
- Data model: Dict with `"mood"`, `"medications"`, `"fuel"`, `"water"`, etc. keys containing lists of entry dicts

**Data Persistence:**
- Atomic writes with temporary file + rename pattern (see `src/chaoscatcher/storage.py`)
- Corruption guards: If JSON parse fails, corrupt file is backed up to `data.corrupt-{timestamp}.json` and reset to `{}`
- Permissions: Data file created with mode 0600 (owner read/write only, no group/other access)

**Caching:**
- None; all data read from disk on each operation
- GUI: In-memory caches for current session (not persisted)

## Authentication & Identity

**Auth Provider:**
- Not applicable — no user accounts, authentication, or identity management
- System is single-user, local-only

## Monitoring & Observability

**Error Tracking:**
- None — no external error reporting

**Logs:**
- Standard output/STDERR for CLI
- Application output logged to stdout in GUI
- No persistent log files by default
- User can redirect output as needed: `chaos mood list > my_log.txt`

## CI/CD & Deployment

**Hosting:**
- None — local application only
- No cloud hosting or remote infrastructure

**CI Pipeline:**
- GitHub Actions (basic setup in `.github/workflows/` if present)
- Pre-commit hooks via `src/chaoscatcher/` + `.pre-commit-config.yaml`
  - Hooks run: `ruff check --fix` and `ruff format` on every commit
  - Configuration: `https://github.com/astral-sh/ruff-pre-commit` rev `v0.15.4`

**Testing:**
- pytest 8.0+ runner
- Tests located in `tests/`
- Run: `pytest`
- Coverage: No coverage requirements enforced

## Environment Configuration

**Required env vars:**
- `CHAOSCATCHER_DATA` (optional) — Override data file location
  - Example: `export CHAOSCATCHER_DATA=~/my-data.json`

**Secrets location:**
- Not applicable — no API keys, tokens, or credentials needed
- `.gitignore` excludes data files to prevent accidental commits of health data

## Data Export Formats

**CSV Export:**
- Supported via CLI and GUI
- Used in `src/chaoscatcher/cli.py` for `mood export --csv` command
- Python standard `csv` module

**JSON Export:**
- Entire data file is JSON; can be exported directly
- GUI supports exporting filtered data views

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Other Integrations

**Desktop Notifications (WSL2-specific):**
- PowerShell audio on WSL2 via subprocess call
- Custom notification popup via `src/chaoscatcher/notification_popup.py` (PySide6 dialog)
- Not external service — all runs locally

**File Dialogs:**
- Qt file dialogs for import/export (PySide6 built-in)
- No external file service

---

*Integration audit: 2026-03-16*

**Summary:** ChaosCatcher is intentionally isolated with no external dependencies. It operates entirely offline with local JSON file storage. This design supports the regulation-centered principle: minimal external complexity, maximum user control.
