from __future__ import annotations

import os
from pathlib import Path


def default_data_path(profile: str | None = None) -> Path:
    base = Path.home() / ".config" / "chaoscatcher"
    name = f"{profile}.json" if profile else "data.json"
    return base / name


def resolve_data_path(data_arg: str | None, profile: str | None) -> Path:
    if data_arg:
        return Path(data_arg).expanduser().resolve()
    env = os.environ.get("CHAOSCATCHER_DATA")
    if env:
        return Path(env).expanduser().resolve()
    return default_data_path(profile).expanduser().resolve()
