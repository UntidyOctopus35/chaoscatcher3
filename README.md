# ChaosCatcher
Regulation-centered self-care logging tool.

Tracks mood, medication, sleep, and water intake in a local JSON file. Includes a CLI (`cc`) and a desktop GUI (`ccgui`).

## Installation

```bash
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
export CHAOSCATCHER_DATA=~/my-data.json   # env var
cc --data ~/my-data.json mood add ...     # per-command flag
cc --profile work mood add ...            # uses ~/.config/chaoscatcher/work.json
```

The data file is never stored inside a git repo (safety guard — prevents accidental commits of health data).

## CLI usage (`cc`)

```bash
cc init                          # create/verify the data file

# Mood
cc mood add --score 7 --tags baseline,school --sleep-total 7:30
cc mood add --score 6 --time "yesterday 9am"
cc mood list
cc mood today
cc mood stats --window 30
cc mood export --csv ~/moods.csv

# Medication
cc med add --name Vyvanse --dose "50 mg" --time "today 7:34am"
cc med today
cc med list
cc med stats --days 14

# Utilities
cc summary
cc where
cc doctor
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
