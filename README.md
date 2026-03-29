
# ChaosCatcher
ChaosCatcher

ChaosCatcher is a regulation-centered self-care logging tool designed to make invisible nervous-system patterns visible.

It tracks mood, medication timing, sleep, hydration, and body signals locally so users can notice drift, overload, and recovery trends early—before they become crises.

ChaosCatcher is not a productivity tracker.
It is a nervous-system awareness tool.

The goal is clarity, stability, and self-understanding—not optimization, streaks, or performance metrics.

Why this exists

Many tracking apps optimize for engagement or behavior change.
ChaosCatcher exists to support:

pattern recognition instead of judgment
regulation instead of productivity
awareness instead of compliance
autonomy instead of surveillance

All data stays local by default.

License and intent

ChaosCatcher is released under the PolyForm Noncommercial License 1.0.0.

You may:

use it
study it
modify it
share it
build on it for personal, educational, or research purposes

You may not use ChaosCatcher or derivatives commercially.

This boundary exists to preserve the project’s purpose as a regulation-centered tool rather than a monetized behavioral product.

What ChaosCatcher tracks

Tracks mood, medication, sleep, and water intake in a local JSON file. Includes a CLI (chaos) and a desktop GUI (ccgui).
Regulation-centered self-care logging tool.


## Installion
git clone https://github.com/UntidyOctopus35/chaoscatcher3.git
cd chaoscatcher3
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
```

## Data file location

By default, data is stored at `~/.config/chaoscatcher/data.json`.

Override with an environment variable or flag:

```bash
export CHAOSCATCHER_DATA=~/my-data.json     # env var
chaos --data ~/my-data.json mood add ...    # per-command flag
chaos --profile work mood add ...           # uses ~/.config/chaoscatcher/work.json
```

The data file is never stored inside a git repo (safety guard — prevents accidental commits of health data).

## CLI usage (`chaos`)

```bash
chaos init                          # create/verify the data file

# Mood
chaos mood add --score 7 --tags baseline,school --sleep-total 7:30
chaos mood add --score 6 --time "yesterday 9am"
chaos mood list
chaos mood today
chaos mood stats --window 30
chaos mood export --csv ~/moods.csv

# Medication
chaos med add --name Vyvanse --dose "50 mg" --time "today 7:34am"
chaos med today
chaos med list
chaos med stats --days 14

# Utilities
chaos summary
chaos where
chaos doctor
```

## GUI usage (`ccgui`)

```bash
ccgui
```

Opens a desktop window (requires tkinter, included with standard Python on most platforms).

## Development

```bash
# Run tests
pytest

# Lint + format check
ruff check .
ruff format --check .

# Auto-fix
ruff check --fix .
ruff format .
```

Pre-commit hooks run `ruff check` and `ruff format` automatically on every commit.
