# ChaosCatcher
Regulation-centered self-care logging tool.

Tracks mood, medication, sleep, and water intake in a local JSON file. Includes a CLI (`chaos`) and a desktop GUI (`ccgui`).

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
