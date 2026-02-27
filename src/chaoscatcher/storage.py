from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict[str, Any]:
    """
    Safe load:
    - creates parent dirs
    - if missing/empty -> writes {}
    - if corrupt -> backs up raw text then resets to {}
    Always returns a dict.
    """
    path = Path(path)
    _ensure_parent(path)

    if not path.exists():
        # create a minimal valid file
        save_json(path, {})
        return {}

    txt = path.read_text(encoding="utf-8").strip()
    if not txt:
        save_json(path, {})
        return {}

    try:
        data = json.loads(txt)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        # corruption guard: backup then reset
        backup = path.with_suffix(f".corrupt-{int(time.time())}.json")
        backup.write_text(txt, encoding="utf-8")
        save_json(path, {})
        return {}


def save_json(path: Path, data: Any) -> None:
    """
    Atomic-ish save:
    - write to temp file in same directory
    - flush + fsync
    - os.replace to target
    - chmod 0600 best-effort
    """
    path = Path(path)
    _ensure_parent(path)

    tmp = path.with_name(path.name + ".tmp")

    payload = json.dumps(
        data,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    ) + "\n"

    with open(tmp, "w", encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp, path)

    try:
        os.chmod(path, 0o600)
    except OSError:
        pass